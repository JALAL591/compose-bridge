package com.composebridge.plugin.services

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.openapi.diagnostic.Logger
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit
import java.util.regex.Pattern

object TailscaleManager {
    private val LOG = Logger.getInstance(TailscaleManager::class.java)
    private val gson = Gson()

    @Volatile
    var isFunnelRunning: Boolean = false
        private set

    @Volatile
    var activeRemoteUrl: String = ""
        private set

    /**
     * Attempts to find the tailscale binary on the host system,
     * prioritizing absolute paths on Windows (C:\Program Files\Tailscale\tailscale.exe).
     */
    fun findTailscaleBinary(): String? {
        val osName = System.getProperty("os.name", "").lowercase()
        if (osName.contains("win")) {
            val candidates = listOf(
                "C:\\Program Files\\Tailscale\\tailscale.exe",
                "C:\\Program Files (x86)\\Tailscale\\tailscale.exe",
                "${System.getenv("LOCALAPPDATA")}\\Tailscale\\tailscale.exe",
                "tailscale"
            )
            for (c in candidates) {
                if (c == "tailscale") {
                    if (canExecute(c)) return c
                } else if (File(c).exists()) {
                    return c
                }
            }
        } else {
            val unixCandidates = listOf(
                "/usr/local/bin/tailscale",
                "/opt/homebrew/bin/tailscale",
                "/usr/bin/tailscale",
                "tailscale"
            )
            for (c in unixCandidates) {
                if (canExecute(c)) return c
            }
        }
        return if (canExecute("tailscale")) "tailscale" else null
    }

    private fun canExecute(cmd: String): Boolean {
        return try {
            val pb = ProcessBuilder(cmd, "version")
            val p = pb.start()
            p.waitFor(1, TimeUnit.SECONDS)
            p.exitValue() == 0
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Starts Tailscale Funnel in the background on the specified local port (default 8711).
     * Uses `tailscale funnel --bg 8711` and queries `tailscale funnel status`.
     * Returns Result with the wss:// public URL (without port suffix).
     */
    fun startFunnel(port: Int = 8711): Result<String> {
        val bin = findTailscaleBinary()
            ?: return Result.failure(IllegalStateException("Tailscale CLI not found. Please install Tailscale from https://tailscale.com/download"))

        try {
            LOG.info("Starting Tailscale Funnel in background on port $port using: $bin")

            // 1. Launch `tailscale funnel --bg 8711`
            val pb = ProcessBuilder(bin, "funnel", "--bg", port.toString())
            pb.redirectErrorStream(true)
            val p = pb.start()

            val launchOutput = StringBuilder()
            val reader = BufferedReader(InputStreamReader(p.inputStream, Charsets.UTF_8))
            var line: String?
            while (reader.readLine().also { line = it } != null) {
                launchOutput.append(line).append("\n")
                LOG.info("[TailscaleFunnelLaunch] $line")
            }
            p.waitFor(5, TimeUnit.SECONDS)

            // 2. Wait 3.5 seconds for background daemon to establish funnel and DNS routing
            try {
                Thread.sleep(3500)
            } catch (_: InterruptedException) {}

            // 3. Query `tailscale funnel status`
            val statusPb = ProcessBuilder(bin, "funnel", "status")
            statusPb.redirectErrorStream(true)
            val statusP = statusPb.start()
            val statusOutput = StringBuilder()
            val statusReader = BufferedReader(InputStreamReader(statusP.inputStream, Charsets.UTF_8))
            var sLine: String?
            while (statusReader.readLine().also { sLine = it } != null) {
                statusOutput.append(sLine).append("\n")
                LOG.info("[TailscaleFunnelStatus] $sLine")
            }
            statusP.waitFor(3, TimeUnit.SECONDS)

            val combined = "$launchOutput\n$statusOutput"

            // 4. Extract hostname (without port suffix, as Funnel terminates SSL at port 443)
            val urlPattern = Pattern.compile("https?://([a-zA-Z0-9.-]+\\.ts\\.net)")
            val matcher = urlPattern.matcher(combined)
            var parsedUrl = ""
            if (matcher.find()) {
                val host = matcher.group(1)
                parsedUrl = "wss://$host/"
            }

            // Fallback: Query `tailscale status --json` to resolve Self.DNSName
            if (parsedUrl.isBlank()) {
                val dns = getTailscaleHostname(bin)
                if (dns.isNotBlank()) {
                    parsedUrl = dns
                }
            }

            if (parsedUrl.isNotBlank()) {
                activeRemoteUrl = parsedUrl
                isFunnelRunning = true
                LOG.info("Tailscale Funnel successfully running at: $activeRemoteUrl")
                return Result.success(activeRemoteUrl)
            }

            return Result.failure(IllegalStateException("Tailscale Funnel started but could not resolve public URL:\n$combined"))
        } catch (e: Exception) {
            LOG.error("Failed to start Tailscale Funnel", e)
            return Result.failure(e)
        }
    }

    /**
     * Resolves the device's public Funnel hostname from `tailscale status --json`.
     * Strips port and returns clean `wss://<node>.<tailnet>.ts.net/`.
     */
    fun getTailscaleHostname(binary: String? = null): String {
        val bin = binary ?: findTailscaleBinary() ?: return ""
        try {
            val pb = ProcessBuilder(bin, "status", "--json")
            val p = pb.start()
            val reader = BufferedReader(InputStreamReader(p.inputStream, Charsets.UTF_8))
            val jsonText = reader.readText()
            p.waitFor(3, TimeUnit.SECONDS)

            val root = gson.fromJson(jsonText, JsonObject::class.java)
            val selfObj = root.getAsJsonObject("Self")
            if (selfObj != null) {
                var dnsName = selfObj.get("DNSName")?.asString ?: ""
                if (dnsName.endsWith(".")) {
                    dnsName = dnsName.substring(0, dnsName.length - 1)
                }
                if (dnsName.isNotBlank()) {
                    return "wss://$dnsName/"
                }
            }
        } catch (e: Exception) {
            LOG.warn("Failed to query tailscale status --json: ${e.message}")
        }
        return ""
    }

    /**
     * Stops Tailscale Funnel by running `tailscale funnel reset` and `tailscale funnel --https=443 off`.
     */
    fun stopFunnel(port: Int = 8711): Boolean {
        val bin = findTailscaleBinary() ?: return false
        return try {
            LOG.info("Stopping Tailscale Funnel on port $port...")
            val pbReset = ProcessBuilder(bin, "funnel", "reset")
            val p1 = pbReset.start()
            p1.waitFor(3, TimeUnit.SECONDS)

            val pbOff = ProcessBuilder(bin, "funnel", "--https=443", "off")
            val p2 = pbOff.start()
            p2.waitFor(3, TimeUnit.SECONDS)

            isFunnelRunning = false
            activeRemoteUrl = ""
            LOG.info("Tailscale Funnel stopped successfully")
            true
        } catch (e: Exception) {
            LOG.error("Failed to stop Tailscale Funnel", e)
            false
        }
    }
}
