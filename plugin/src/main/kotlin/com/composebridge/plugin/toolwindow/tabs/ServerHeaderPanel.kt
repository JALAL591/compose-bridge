package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.BridgeServerManager
import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.services.TailscaleManager
import com.composebridge.plugin.settings.ComposeBridgeConfigurable
import com.composebridge.plugin.settings.ComposeBridgeSettings
import com.composebridge.plugin.toolwindow.RemoteShareDialog
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.openapi.options.ShowSettingsUtil
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import java.awt.*
import java.awt.datatransfer.StringSelection
import java.io.File
import javax.swing.*

class ServerHeaderPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner,
    private val onScanProjectClicked: () -> Unit,
    private val onRefreshChangesNeeded: () -> Unit
) : JPanel() {

    private val gson = Gson()
    private var lastNotifiedApkTime: Double = 0.0

    // Bridge Server Toolbar Controls
    val startBridgeButton = BridgeUiUtils.createStyledButton("Start Bridge", BridgeColors.btnGreen, Color.WHITE)
    val stopBridgeButton = BridgeUiUtils.createStyledButton("Stop Bridge", BridgeColors.btnRed, Color.WHITE).apply {
        isVisible = false
    }
    val shareRemoteButton = BridgeUiUtils.createStyledButton("Share Remote", Color(0x1D, 0x4E, 0xD8), Color.WHITE).apply {
        toolTipText = "Share Bridge over Tailscale Funnel and generate QR Code"
        addActionListener { onShareRemote() }
    }
    val tokenButton = BridgeUiUtils.createStyledButton("Token", BridgeColors.btnGray, Color.WHITE).apply {
        toolTipText = "Copy current dynamic auth token to clipboard"
        addActionListener {
            val token = BridgeServerManager.readAuthToken(project.basePath)
            if (token.isNotBlank()) {
                val sel = StringSelection(token)
                Toolkit.getDefaultToolkit().systemClipboard.setContents(sel, sel)
                Messages.showInfoMessage("Copied dynamic auth token to clipboard!", "ComposeBridge")
            } else {
                Messages.showWarningDialog("No active auth token found. Start Bridge Server first.", "ComposeBridge")
            }
        }
    }

    val deviceStatusLabel = JLabel("Device: Disconnected").apply {
        font = Font("Segoe UI", Font.BOLD, 12)
        foreground = BridgeColors.textMuted
    }

    val apkBuildStatusLabel = JLabel("").apply {
        font = Font("Segoe UI", Font.BOLD, 12)
        foreground = BridgeColors.textMuted
        isVisible = false
    }

    val bridgeStatusLabel = JLabel("Bridge Stopped").apply {
        font = Font("Segoe UI", Font.BOLD, 12)
        foreground = Color(0xF8, 0x71, 0x71)
    }

    // Sync Toolbar Controls
    val syncButton = BridgeUiUtils.createStyledButton("Sync Now", BridgeColors.btnGray, Color.WHITE)
    val syncStatusLabel = JLabel(" ")
    val queueCountBadge = JLabel(" ")

    init {
        layout = BoxLayout(this, BoxLayout.Y_AXIS)
        background = BridgeColors.bgDark
        border = BorderFactory.createCompoundBorder(
            BorderFactory.createMatteBorder(0, 0, 1, 0, BridgeColors.bgHeader),
            BorderFactory.createEmptyBorder(4, 8, 4, 8)
        )

        // Row 1: Action Buttons
        val buttonsRow = JPanel(FlowLayout(FlowLayout.LEFT, 8, 2)).apply {
            isOpaque = false
        }
        val scanButton = BridgeUiUtils.createStyledButton("Scan Project", BridgeColors.accentBlue, Color.WHITE)
        scanButton.addActionListener { onScanProjectClicked() }

        startBridgeButton.toolTipText = "Start Bridge Server (python server.py) and setup adb reverse"
        startBridgeButton.addActionListener { onStartBridge() }

        stopBridgeButton.toolTipText = "Stop running Bridge Server"
        stopBridgeButton.addActionListener { onStopBridge() }

        syncButton.addActionListener { onTriggerSync() }
        syncButton.toolTipText = "Apply queued edits to files"

        val settingsButton = BridgeUiUtils.createStyledButton("Settings", BridgeColors.btnGray, Color.WHITE).apply {
            toolTipText = "Configure Python and Bridge paths"
            addActionListener {
                ShowSettingsUtil.getInstance().showSettingsDialog(project, ComposeBridgeConfigurable::class.java)
            }
        }

        val cleanCacheButton = BridgeUiUtils.createStyledButton("Clean Cache", Color(0xD9, 0x77, 0x06), Color.WHITE).apply {
            toolTipText = "Clean Temporary Cache & Logs (Safe)"
            addActionListener { onCleanCache() }
        }

        buttonsRow.add(scanButton)
        buttonsRow.add(startBridgeButton)
        buttonsRow.add(stopBridgeButton)
        buttonsRow.add(shareRemoteButton)
        buttonsRow.add(tokenButton)
        buttonsRow.add(syncButton)
        buttonsRow.add(settingsButton)
        buttonsRow.add(cleanCacheButton)
        add(buttonsRow)

        // Row 2: Status Badges / Notifications
        val statusRow = JPanel(FlowLayout(FlowLayout.LEFT, 12, 2)).apply {
            isOpaque = false
            border = BorderFactory.createEmptyBorder(1, 4, 2, 4)
        }
        bridgeStatusLabel.font = Font("Segoe UI", Font.BOLD, 11)
        deviceStatusLabel.font = Font("Segoe UI", Font.BOLD, 11)
        apkBuildStatusLabel.font = Font("Segoe UI", Font.PLAIN, 11)
        queueCountBadge.foreground = Color(0xE5, 0x51, 0x00)
        queueCountBadge.font = queueCountBadge.font.deriveFont(Font.BOLD, 11f)
        syncStatusLabel.foreground = BridgeColors.textMuted
        syncStatusLabel.font = Font("Segoe UI", Font.PLAIN, 11)

        val statusLabel = JLabel("Ready").apply {
            foreground = BridgeColors.textMuted
            font = Font("Segoe UI", Font.PLAIN, 11)
        }

        statusRow.add(bridgeStatusLabel)
        statusRow.add(deviceStatusLabel)
        statusRow.add(apkBuildStatusLabel)
        statusRow.add(queueCountBadge)
        statusRow.add(syncStatusLabel)
        statusRow.add(statusLabel)
        add(statusRow)

        updateBridgeStatusUi(BridgeServerManager.isRunning())
    }

    fun updateBridgeStatusUi(running: Boolean) {
        if (running) {
            startBridgeButton.isVisible = false
            stopBridgeButton.isVisible = true
            bridgeStatusLabel.text = "Bridge Running"
            bridgeStatusLabel.foreground = BridgeColors.statusGreen

            val deviceStatus = BridgeServerManager.readDeviceStatus(project.basePath)
            if (deviceStatus.connected) {
                deviceStatusLabel.text = "Device: Connected (${deviceStatus.count})"
                deviceStatusLabel.foreground = BridgeColors.statusGreen
            } else {
                deviceStatusLabel.text = "Device: Waiting..."
                deviceStatusLabel.foreground = Color(0xF5, 0x9E, 0x0B)
            }

            val apkStatus = BridgeServerManager.readApkBuildStatus(project.basePath)
            if (apkStatus != null && apkStatus.updatedAt > 0) {
                val ageSec = (System.currentTimeMillis() / 1000.0) - apkStatus.updatedAt
                if (apkStatus.building) {
                    apkBuildStatusLabel.text = "Building APK..."
                    apkBuildStatusLabel.foreground = Color(0x0E, 0xA5, 0xE9)
                    apkBuildStatusLabel.toolTipText = apkStatus.message
                    apkBuildStatusLabel.isVisible = true
                } else if (apkStatus.success && ageSec < 1800) {
                    apkBuildStatusLabel.text = "APK: ${apkStatus.fileName}"
                    apkBuildStatusLabel.foreground = BridgeColors.statusGreen
                    apkBuildStatusLabel.toolTipText = apkStatus.filePath
                    apkBuildStatusLabel.isVisible = true

                    if (apkStatus.updatedAt > lastNotifiedApkTime) {
                        lastNotifiedApkTime = apkStatus.updatedAt
                        try {
                            com.intellij.notification.NotificationGroupManager.getInstance()
                                .getNotificationGroup("ComposeBridge Notifications")
                                ?.createNotification(
                                    "ComposeBridge APK Build",
                                    "✅ APK built successfully: ${apkStatus.fileName}",
                                    com.intellij.notification.NotificationType.INFORMATION
                                )?.notify(project)
                        } catch (_: Exception) {}
                    }
                } else if (apkStatus.stage == "error" && ageSec < 1800) {
                    apkBuildStatusLabel.text = "Build Failed"
                    apkBuildStatusLabel.foreground = Color(0xEF, 0x44, 0x44)
                    apkBuildStatusLabel.toolTipText = apkStatus.message
                    apkBuildStatusLabel.isVisible = true
                } else {
                    apkBuildStatusLabel.isVisible = false
                }
            } else {
                apkBuildStatusLabel.isVisible = false
            }
        } else {
            startBridgeButton.isVisible = true
            stopBridgeButton.isVisible = false
            bridgeStatusLabel.text = "Bridge Stopped"
            bridgeStatusLabel.foreground = Color(0xF8, 0x71, 0x71)
            deviceStatusLabel.text = "Device: Disconnected"
            deviceStatusLabel.foreground = BridgeColors.textMuted
        }
    }

    fun onStartBridge() {
        val bridgePath = pythonRunner.getBridgePath()
        if (bridgePath.isBlank() || !File(bridgePath).exists()) {
            val res = Messages.showYesNoDialog(
                project,
                "Bridge directory is not configured or does not exist. Open Settings?",
                "ComposeBridge",
                "Open Settings",
                "Cancel",
                Messages.getWarningIcon()
            )
            if (res == Messages.YES) {
                ShowSettingsUtil.getInstance().showSettingsDialog(project, ComposeBridgeConfigurable::class.java)
            }
            return
        }

        startBridgeButton.isEnabled = false
        bridgeStatusLabel.text = "Starting Bridge..."
        bridgeStatusLabel.foreground = Color(0xFB, 0xBF, 0x24)

        val settings = ComposeBridgeSettings.getInstance(project)
        val pythonExec = settings.state.pythonPath
        val projectRoot = project.basePath

        Thread {
            val started = BridgeServerManager.startServer(
                bridgePath = bridgePath,
                pythonPath = pythonExec,
                projectRoot = projectRoot
            ) { isRunning ->
                SwingUtilities.invokeLater {
                    updateBridgeStatusUi(isRunning)
                }
            }

            SwingUtilities.invokeLater {
                startBridgeButton.isEnabled = true
                updateBridgeStatusUi(BridgeServerManager.isRunning())
                if (!started) {
                    Messages.showErrorDialog(
                        project,
                        "Failed to start Bridge Server (server.py).\nPlease verify python executable and dependencies in Settings.",
                        "ComposeBridge Error"
                    )
                }
            }
        }.start()
    }

    fun onStopBridge() {
        stopBridgeButton.isEnabled = false
        bridgeStatusLabel.text = "Stopping..."
        bridgeStatusLabel.foreground = Color(0xFB, 0xBF, 0x24)

        Thread {
            TailscaleManager.stopFunnel(8711)
            BridgeServerManager.stopServer { isRunning ->
                SwingUtilities.invokeLater {
                    updateBridgeStatusUi(isRunning)
                }
            }
            SwingUtilities.invokeLater {
                stopBridgeButton.isEnabled = true
                updateBridgeStatusUi(BridgeServerManager.isRunning())
            }
        }.start()
    }

    fun onShareRemote() {
        val projectRoot = project.basePath ?: return

        if (TailscaleManager.isFunnelRunning) {
            val options = arrayOf("View QR Code", "Stop Sharing", "Cancel")
            val sel = Messages.showDialog(
                project,
                "Tailscale Funnel is currently active at:\n${TailscaleManager.activeRemoteUrl}",
                "ComposeBridge Remote Access",
                options,
                0,
                Messages.getInformationIcon()
            )
            when (sel) {
                0 -> {
                    val token = BridgeServerManager.readAuthToken(projectRoot)
                    RemoteShareDialog(project, TailscaleManager.activeRemoteUrl, token) {
                        TailscaleManager.stopFunnel(8711)
                        bridgeStatusLabel.text = "Bridge Running"
                    }.show()
                }
                1 -> {
                    TailscaleManager.stopFunnel(8711)
                    bridgeStatusLabel.text = "Bridge Running"
                    Messages.showInfoMessage("Tailscale Funnel stopped.", "ComposeBridge")
                }
            }
            return
        }

        if (!BridgeServerManager.isRunning()) {
            val choice = Messages.showYesNoDialog(
                project,
                "Bridge Server is not running. Would you like to start it now?",
                "ComposeBridge Remote Access",
                Messages.getQuestionIcon()
            )
            if (choice == Messages.YES) {
                onStartBridge()
                Thread.sleep(1200)
            } else {
                return
            }
        }

        val token = BridgeServerManager.readAuthToken(projectRoot)

        val bin = TailscaleManager.findTailscaleBinary()
        if (bin == null) {
            val manualUrl = Messages.showInputDialog(
                project,
                "Tailscale CLI was not found in PATH or standard directories.\n\n" +
                "You can install Tailscale from https://tailscale.com/download\n" +
                "Or enter your public WebSocket URL manually (e.g. wss://my-node.ts.net):",
                "ComposeBridge Remote Access",
                Messages.getInformationIcon(),
                "wss://",
                null
            )
            if (!manualUrl.isNullOrBlank() && manualUrl != "wss://") {
                RemoteShareDialog(project, manualUrl.trim(), token).show()
            }
            return
        }

        Thread {
            SwingUtilities.invokeLater {
                bridgeStatusLabel.text = "Starting Funnel..."
            }
            val result = TailscaleManager.startFunnel(8711)
            SwingUtilities.invokeLater {
                result.fold(
                    onSuccess = { url ->
                        bridgeStatusLabel.text = "Remote: $url"
                        RemoteShareDialog(project, url, token) {
                            TailscaleManager.stopFunnel(8711)
                            bridgeStatusLabel.text = "Bridge Running"
                        }.show()
                    },
                    onFailure = { err ->
                        bridgeStatusLabel.text = "Tailscale Error"
                        val manualUrl = Messages.showInputDialog(
                            project,
                            "Failed to start Tailscale Funnel automatically: ${err.message}\n\n" +
                            "Make sure 'tailscale funnel' is enabled on your Tailnet.\n" +
                            "Or enter your public URL manually to generate a QR Code:",
                            "Tailscale Funnel Error",
                            Messages.getWarningIcon(),
                            "wss://",
                            null
                        )
                        if (!manualUrl.isNullOrBlank() && manualUrl != "wss://") {
                            RemoteShareDialog(project, manualUrl.trim(), token).show()
                        }
                    }
                )
            }
        }.start()
    }

    private fun onTriggerSync() {
        syncButton.isEnabled = false
        syncStatusLabel.text = "Syncing..."
        syncStatusLabel.foreground = BridgeColors.textMuted
        syncButton.text = "Syncing..."

        Thread {
            val json = pythonRunner.triggerUserSync()
            SwingUtilities.invokeLater {
                syncButton.isEnabled = true
                syncButton.text = "Sync Now"
                parseSyncResult(json)
            }
        }.start()
    }

    private fun parseSyncResult(json: String) {
        try {
            val cleanJson = BridgeUiUtils.extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")

            if (success) {
                val applied = root.get("applied")?.asInt ?: 0
                val skipped = root.get("skipped")?.asInt ?: 0
                val errors = root.get("errors")?.asInt ?: 0
                val status = root.get("status")?.asString ?: ""

                when (status) {
                    "refused" -> {
                        syncStatusLabel.text = "Agent busy — cannot sync now"
                        syncStatusLabel.foreground = Color(0xE5, 0x51, 0x00)
                    }
                    "partial" -> {
                        syncStatusLabel.text = "Applied $applied | Failed $skipped"
                        syncStatusLabel.foreground = Color(0xE5, 0x51, 0x00)
                    }
                    else -> {
                        if (applied == 0) {
                            syncStatusLabel.text = "No pending edits"
                            syncStatusLabel.foreground = BridgeColors.textMuted
                        } else {
                            syncStatusLabel.text = "Synced $applied edit(s)"
                            syncStatusLabel.foreground = BridgeColors.statusGreen
                        }
                    }
                }

                queueCountBadge.text = " "
                onRefreshChangesNeeded()
            } else {
                val error = root.get("error")?.asString ?: "Unknown error"
                syncStatusLabel.text = "Error: $error"
                syncStatusLabel.foreground = Color(0xC6, 0x28, 0x28)
            }
        } catch (e: Exception) {
            syncStatusLabel.text = "Error: Parse error: ${e.message}"
            syncStatusLabel.foreground = Color(0xC6, 0x28, 0x28)
        }
    }

    fun updateQueueBadge(count: Int) {
        if (count > 0) {
            queueCountBadge.text = "$count queued"
        } else {
            queueCountBadge.text = " "
        }
    }

    fun refreshSyncStatus() {
        Thread {
            val json = pythonRunner.getSyncStatus()
            SwingUtilities.invokeLater {
                try {
                    val cleanJson = BridgeUiUtils.extractJson(json)
                    val root = gson.fromJson(cleanJson, JsonObject::class.java)
                    val queueCount = root.get("queue_count")?.asInt ?: 0
                    val agentBusy = root.get("agent_busy")?.asBoolean ?: false

                    updateQueueBadge(queueCount)

                    if (agentBusy) {
                        syncStatusLabel.text = "Agent busy"
                        syncStatusLabel.foreground = Color(0xE5, 0x51, 0x00)
                    } else if (queueCount > 0) {
                        syncStatusLabel.text = "Ready to sync"
                        syncStatusLabel.foreground = BridgeColors.statusGreen
                    } else {
                        syncStatusLabel.text = " "
                    }
                } catch (e: Exception) {
                    // ignore if server not running
                }
            }
        }.start()
    }

    private fun onCleanCache() {
        val choice = Messages.showYesNoDialog(
            "This will clear temporary cache and logs. If there are pending edits, they will be lost. Continue?",
            "Clean Temporary Cache & Logs",
            Messages.getQuestionIcon()
        )
        if (choice != Messages.YES) return

        Thread {
            val json = pythonRunner.cleanTempFiles()
            SwingUtilities.invokeLater {
                try {
                    val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
                    if (root.get("success")?.asBoolean == true) {
                        try {
                            val statusBar = com.intellij.openapi.wm.WindowManager.getInstance().getStatusBar(project)
                            val comp = statusBar?.component
                            if (comp != null) {
                                com.intellij.openapi.ui.popup.JBPopupFactory.getInstance()
                                    .createHtmlTextBalloonBuilder(
                                        "Cache cleaned successfully. You may need to re-scan the project.",
                                        com.intellij.openapi.ui.MessageType.INFO,
                                        null
                                    )
                                    .setFadeoutTime(5000)
                                    .createBalloon()
                                    .show(
                                        com.intellij.ui.awt.RelativePoint.getCenterOf(comp),
                                        com.intellij.openapi.ui.popup.Balloon.Position.above
                                    )
                            } else {
                                Messages.showInfoMessage(
                                    "Cache cleaned successfully. You may need to re-scan the project.",
                                    "ComposeBridge"
                                )
                            }
                        } catch (_: Exception) {
                            Messages.showInfoMessage(
                                "Cache cleaned successfully. You may need to re-scan the project.",
                                "ComposeBridge"
                            )
                        }
                    } else {
                        val err = root.get("error")?.asString ?: "Failed to clean cache."
                        Messages.showErrorDialog(err, "ComposeBridge - Clean Cache Error")
                    }
                } catch (e: Exception) {
                    Messages.showErrorDialog("Error cleaning cache: ${e.message}", "ComposeBridge")
                }
                onRefreshChangesNeeded()
            }
        }.start()
    }
}

