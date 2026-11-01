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

    @Volatile
    var currentAuthToken: String = ""

    @Volatile
    private var isManuallyStopped: Boolean = false

    @Volatile
    private var lastBridgePath: String = ""

    @Volatile
    private var lastPythonPath: String = "python"

    @Volatile
    private var lastProjectRoot: String? = null

    @Volatile
    private var lastOnStatusChange: ((Boolean) -> Unit)? = null

    fun findAdbExecutable(): String {
        val candidates = listOfNotNull(
            System.getenv("ANDROID_HOME")?.let { File(it, "platform-tools/adb.exe") },
            System.getenv("ANDROID_SDK_ROOT")?.let { File(it, "platform-tools/adb.exe") },
            System.getenv("LOCALAPPDATA")?.let { File(it, "Android/Sdk/platform-tools/adb.exe") },
            System.getProperty("user.home")?.let { File(it, "AppData/Local/Android/Sdk/platform-tools/adb.exe") },
            System.getenv("ANDROID_HOME")?.let { File(it, "platform-tools/adb") },
            System.getenv("ANDROID_SDK_ROOT")?.let { File(it, "platform-tools/adb") },
            System.getProperty("user.home")?.let { File(it, "Android/Sdk/platform-tools/adb") }
        )
        for (f in candidates) {
            if (f.exists() && f.canExecute()) {
                return f.absolutePath
            }
        }
        return "adb"
    }

    fun readAuthToken(projectRoot: String? = null, forceReload: Boolean = false): String {
        if (!forceReload && currentAuthToken.isNotBlank()) return currentAuthToken

        if (!projectRoot.isNullOrBlank()) {
            val projectTokenFile = File(projectRoot, ".composebridge-state/auth_token.txt")
            if (projectTokenFile.exists()) {
                val t = projectTokenFile.readText(Charsets.UTF_8).trim()
                if (t.isNotBlank()) {
                    currentAuthToken = t
                    return t
                }
            }
        }

        val homeTokenFile = File(System.getProperty("user.home"), ".composebridge-state/auth_token.txt")
        if (homeTokenFile.exists()) {
            val t = homeTokenFile.readText(Charsets.UTF_8).trim()
            if (t.isNotBlank()) {
                currentAuthToken = t
                return t
            }
        }

        return ""
    }

    
    data class ApkBuildStatus(
        val building: Boolean,
        val stage: String,
        val progress: Float,
        val message: String,
        val success: Boolean,
        val fileName: String,
        val filePath: String,
        val updatedAt: Double
    )

    fun readApkBuildStatus(projectRoot: String? = null): ApkBuildStatus? {
        if (!projectRoot.isNullOrBlank()) {
            val statusFile = File(projectRoot, ".composebridge-state/apk_build_status.json")
            if (statusFile.exists()) {
                try {
                    val text = statusFile.readText(Charsets.UTF_8).trim()
                    if (text.isNotBlank()) {
                        val obj = com.google.gson.JsonParser.parseString(text).asJsonObject
                        return ApkBuildStatus(
                            building = obj.get("building")?.asBoolean ?: false,
                            stage = obj.get("stage")?.asString ?: "",
                            progress = obj.get("progress")?.asFloat ?: 0f,
                            message = obj.get("message")?.asString ?: "",
                            success = obj.get("success")?.asBoolean ?: false,
                            fileName = obj.get("file_name")?.asString ?: "",
                            filePath = obj.get("file_path")?.asString ?: "",
                            updatedAt = obj.get("updated_at")?.asDouble ?: 0.0
                        )
                    }
                } catch (_: Exception) {}
            }
        }
        val homeFile = File(System.getProperty("user.home"), ".composebridge-state/apk_build_status.json")
        if (homeFile.exists()) {
            try {
                val text = homeFile.readText(Charsets.UTF_8).trim()
                if (text.isNotBlank()) {
                    val obj = com.google.gson.JsonParser.parseString(text).asJsonObject
                    return ApkBuildStatus(
                        building = obj.get("building")?.asBoolean ?: false,
                        stage = obj.get("stage")?.asString ?: "",
                        progress = obj.get("progress")?.asFloat ?: 0f,
                        message = obj.get("message")?.asString ?: "",
                        success = obj.get("success")?.asBoolean ?: false,
                        fileName = obj.get("file_name")?.asString ?: "",
                        filePath = obj.get("file_path")?.asString ?: "",
                        updatedAt = obj.get("updated_at")?.asDouble ?: 0.0
                    )
                }
            } catch (_: Exception) {}
        }
        return null
    }

    data class DeviceStatus(val connected: Boolean, val count: Int)

    fun readDeviceStatus(projectRoot: String? = null): DeviceStatus {
        if (!projectRoot.isNullOrBlank()) {
            val statusFile = File(projectRoot, ".composebridge-state/device_status.json")
            if (statusFile.exists()) {
                try {
                    val text = statusFile.readText(Charsets.UTF_8).trim()
                    if (text.isNotBlank()) {
                        val obj = com.google.gson.JsonParser.parseString(text).asJsonObject
                        val connected = obj.get("connected")?.asBoolean ?: false
                        val count = obj.get("count")?.asInt ?: 0
                        return DeviceStatus(connected, count)
                    }
                } catch (_: Exception) {}
            }
        }
        val homeFile = File(System.getProperty("user.home"), ".composebridge-state/device_status.json")
        if (homeFile.exists()) {
            try {
                val text = homeFile.readText(Charsets.UTF_8).trim()
                if (text.isNotBlank()) {
                    val obj = com.google.gson.JsonParser.parseString(text).asJsonObject
                    val connected = obj.get("connected")?.asBoolean ?: false
                    val count = obj.get("count")?.asInt ?: 0
                    return DeviceStatus(connected, count)
                }
            } catch (_: Exception) {}
        }
        return DeviceStatus(false, 0)
    }

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

        currentAuthToken = ""
        isManuallyStopped = false
        lastBridgePath = bridgePath
        lastPythonPath = pythonExec
        lastProjectRoot = projectRoot
        lastOnStatusChange = onStatusChange

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
                    val tokenRegex = Regex("[a-fA-F0-9]{32,64}")
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        val currentLine = line ?: ""
                        LOG.info("[BridgeServer] $currentLine")
                        if (currentLine.contains("Auth Token:")) {
                            val match = tokenRegex.find(currentLine.substringAfter("Auth Token:"))
                            if (match != null) {
                                val extractedToken = match.value
                                if (extractedToken != currentAuthToken) {
                                    currentAuthToken = extractedToken
                                    LOG.info("Extracted active Auth Token from server stdout: ${extractedToken.take(8)}...")
                                    runAdbReverse(extractedToken)
                                }
                            }
                        }
                    }
                } catch (e: Exception) {
                    LOG.debug("BridgeServer output reader terminated: ${e.message}")
                } finally {
                    onStatusChange?.invoke(false)
                    if (!isManuallyStopped) {
                        LOG.warn("Bridge Server exited unexpectedly! Watchdog will auto-restart in 2 seconds...")
                        Thread({
                            try {
                                Thread.sleep(2000)
                                if (!isManuallyStopped && !isRunning() && lastBridgePath.isNotBlank()) {
                                    LOG.info("Watchdog triggering auto-restart of Bridge Server...")
                                    startServer(lastBridgePath, lastPythonPath, lastProjectRoot, lastOnStatusChange)
                                }
                            } catch (_: Exception) {}
                        }, "ComposeBridge-Server-Watchdog").start()
                    }
                }
            }, "ComposeBridge-Server-Logger")
            readerThread.isDaemon = true
            readerThread.start()

            // Brief pause to detect immediate startup crash and read token
            Thread.sleep(500)
            if (!process.isAlive) {
                LOG.error("Bridge Server process failed to stay alive after launch")
                serverProcess = null
                onStatusChange?.invoke(false)
                return false
            }

            val token = if (currentAuthToken.isNotBlank()) currentAuthToken else readAuthToken(projectRoot, forceReload = true)
            if (token.isNotBlank()) {
                currentAuthToken = token
                LOG.info("Bridge Server Auth Token: ${token.take(8)}...")
                runAdbReverse(token)
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
        isManuallyStopped = true
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

    fun runAdbReverse(token: String? = null) {
        Thread({
            try {
                val adbPath = findAdbExecutable()
                val adbPb = ProcessBuilder(adbPath, "reverse", "tcp:8711", "tcp:8711")
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

                // If auth token is present, broadcast to app via ADB
                val activeToken = if (!token.isNullOrBlank()) token else currentAuthToken
                if (activeToken.isNotBlank()) {
                    try {
                        val broadcastPb = ProcessBuilder(
                            adbPath, "shell", "am", "broadcast",
                            "-a", "com.composebridge.SET_TOKEN",
                            "--es", "token", activeToken
                        )
                        broadcastPb.start().waitFor(3, TimeUnit.SECONDS)
                        LOG.info("Broadcasted auth token to device via ADB")
                    } catch (be: Exception) {
                        LOG.debug("ADB token broadcast notice: ${be.message}")
                    }
                }
            } catch (e: Exception) {
                LOG.warn("adb reverse execution failed: ${e.message}")
            }
        }, "ComposeBridge-Adb-Reverse").start()
    }
}
