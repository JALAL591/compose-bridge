package com.composebridge.plugin.services

import com.intellij.openapi.diagnostic.Logger
import java.io.BufferedReader
import java.io.File
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit

object BridgeServerManager {
    private val LOG = Logger.getInstance(BridgeServerManager::class.java)

    @Volatile
    private var serverProcess: Process? = null

    @Synchronized
    fun isRunning(): Boolean {
        val p = serverProcess
        return p != null && p.isAlive
    }

    @Synchronized
    fun startServer(
        bridgePath: String,
        pythonPath: String = "python",
        projectRoot: String? = null,
        onStatusChange: ((Boolean) -> Unit)? = null
    ): Boolean {
        if (isRunning()) {
            onStatusChange?.invoke(true)
            return true
        }

        if (bridgePath.isBlank()) {
            LOG.warn("Cannot start Bridge Server: bridgePath is blank")
            onStatusChange?.invoke(false)
            return false
        }

        val bridgeDir = File(bridgePath)
        val serverScript = File(bridgeDir, "server.py")
        if (!serverScript.exists()) {
            LOG.warn("Cannot start Bridge Server: server.py not found at $bridgePath")
            onStatusChange?.invoke(false)
            return false
        }

        val pythonExec = if (pythonPath.isNotBlank()) pythonPath else "python"

        try {
            // 1. Run adb reverse tcp:8711 tcp:8711
            runAdbReverse()

            // 2. Launch python server.py
            val pb = ProcessBuilder(pythonExec, "server.py")
            pb.directory(bridgeDir)
            if (!projectRoot.isNullOrBlank()) {
                pb.environment()["COMPOSEBRIDGE_ROOT"] = projectRoot
            }
            pb.environment()["PYTHONUNBUFFERED"] = "1"
            pb.environment()["PYTHONIOENCODING"] = "utf-8"
            pb.environment()["PYTHONUTF8"] = "1"
            pb.redirectErrorStream(true)

            val process = pb.start()
            serverProcess = process

            // 3. Read stdout/stderr in background thread
            val readerThread = Thread({
                try {
                    val reader = BufferedReader(InputStreamReader(process.inputStream, Charsets.UTF_8))
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        LOG.info("[BridgeServer] $line")
                    }
                } catch (e: Exception) {
                    LOG.debug("BridgeServer output reader terminated: ${e.message}")
                } finally {
                    onStatusChange?.invoke(false)
                }
            }, "ComposeBridge-Server-Logger")
            readerThread.isDaemon = true
            readerThread.start()

            // Brief pause to detect immediate startup crash
            Thread.sleep(400)
            if (!process.isAlive) {
                LOG.error("Bridge Server process failed to stay alive after launch")
                serverProcess = null
                onStatusChange?.invoke(false)
                return false
            }

            onStatusChange?.invoke(true)
            return true
        } catch (e: Exception) {
            LOG.error("Failed to start Bridge Server", e)
            serverProcess = null
            onStatusChange?.invoke(false)
            return false
        }
    }

    @Synchronized
    fun stopServer(onStatusChange: ((Boolean) -> Unit)? = null) {
        val p = serverProcess ?: run {
            onStatusChange?.invoke(false)
            return
        }
        try {
            LOG.info("Stopping Bridge Server process...")
            p.destroy()
            val exited = p.waitFor(2, TimeUnit.SECONDS)
            if (!exited) {
                p.destroyForcibly()
            }
        } catch (e: Exception) {
            LOG.error("Error stopping Bridge Server process", e)
            try {
                p.destroyForcibly()
            } catch (_: Exception) {}
        } finally {
            serverProcess = null
            onStatusChange?.invoke(false)
        }
    }

    fun runAdbReverse() {
        Thread({
            try {
                val adbPb = ProcessBuilder("adb", "reverse", "tcp:8711", "tcp:8711")
                val process = adbPb.start()
                val exited = process.waitFor(3, TimeUnit.SECONDS)
                if (exited) {
                    val code = process.exitValue()
                    if (code == 0) {
                        LOG.info("adb reverse tcp:8711 tcp:8711 executed successfully")
                    } else {
                        LOG.warn("adb reverse returned exit code $code")
                    }
                } else {
                    process.destroyForcibly()
                    LOG.warn("adb reverse timed out after 3 seconds")
                }
            } catch (e: Exception) {
                LOG.warn("adb reverse execution failed: ${e.message}")
            }
        }, "ComposeBridge-Adb-Reverse").start()
    }
}
