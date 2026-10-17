package com.composebridge.plugin.toolwindow

import com.composebridge.plugin.services.BridgeServerManager
import com.composebridge.plugin.settings.ComposeBridgeSettings
import com.intellij.openapi.util.Disposer

import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.settings.ComposeBridgeConfigurable
import com.intellij.openapi.options.ShowSettingsUtil
import java.io.File
import com.google.gson.Gson
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.content.ContentFactory
import com.intellij.ui.table.JBTable
import java.awt.*
import javax.swing.*
import javax.swing.table.DefaultTableCellRenderer
import javax.swing.table.DefaultTableModel

class ComposeBridgeToolWindowFactory : ToolWindowFactory, DumbAware {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = ComposeBridgePanel(project)
        val content = ContentFactory.getInstance().createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
        Disposer.register(toolWindow.disposable) {
            BridgeServerManager.stopServer()
        }
    }

    override fun shouldBeAvailable(project: Project): Boolean = true
}

data class SharedToken(val name: String, val value: String, val usage: Int)

class ComposeBridgePanel(private val project: Project) : JPanel(BorderLayout()) {

    private val pythonRunner = PythonRunner(project)
    private val gson = Gson()

    // Color Palette matching design
    private val bgMain = Color(0x2B, 0x2D, 0x30)
    private val bgDark = Color(0x1E, 0x1F, 0x22)
    private val bgTabBar = Color(0x24, 0x25, 0x28)
    private val bgHeader = Color(0x27, 0x28, 0x2C)
    private val bgRowAlt = Color(0x21, 0x22, 0x26)
    private val bgSelected = Color(0x2E, 0x43, 0x6E)
    private val textPrimary = Color(0xDF, 0xE1, 0xE5)
    private val textMuted = Color(0x9B, 0x9F, 0xA6)
    private val accentBlue = Color(0x35, 0x74, 0xF0)
    private val statusGreen = Color(0x4A, 0xDE, 0x80)
    private val btnGreen = Color(0x16, 0x65, 0x34)
    private val btnRed = Color(0x99, 0x1B, 0x1B)
    private val btnRollback = Color(0x78, 0x23, 0x2D)
    private val btnGray = Color(0x37, 0x41, 0x51)
    private val badgeRed = Color(0xDC, 0x50, 0x50)

    // Bridge Server Toolbar Controls
    private val startBridgeButton = createStyledButton("▶ Start Bridge", btnGreen, Color.WHITE)
    private val stopBridgeButton = createStyledButton("⏹ Stop Bridge", btnRed, Color.WHITE).apply {
        isVisible = false
    }
    private val bridgeStatusLabel = JLabel("🔴 Bridge Stopped").apply {
        font = Font("Segoe UI", Font.BOLD, 12)
        foreground = Color(0xF8, 0x71, 0x71)
    }

    // Sync Toolbar Controls
    private val syncButton = createStyledButton("🔄 Sync Now", btnGray, Color.WHITE)
    private val syncStatusLabel = JLabel(" ")
    private val queueCountBadge = JLabel(" ")

    private val tabbedPane = JTabbedPane()

    // Scan Tab
    private val scanTableModel = DefaultTableModel(
        arrayOf("Name", "Value", "Location", "Type"), 0
    )
    private val scanTable = JBTable(scanTableModel)
    private val siblingsPanel = JPanel(FlowLayout(FlowLayout.LEFT))
    private val siblingsTitleLabel = JLabel("🔗 Related tokens: ")

    // Impact Tab
    private val impactTitleLabel = JLabel("Select a token from Scan tab to see impact")
    private val impactTableModel = DefaultTableModel(
        arrayOf("File", "Line", "Content", "Composable"), 0
    )
    private val impactTable = JBTable(impactTableModel)
    private val impactSummaryLabel = JLabel(" ")

    // Split Tab
    private val splitTableModel = DefaultTableModel(
        arrayOf("Token", "Value", "Contexts", "Suggested Tokens"), 0
    )
    private val splitTable = JBTable(splitTableModel)
    private val splitSummaryLabel = JLabel("Press 'Scan Project' to see split suggestions")

    // Patterns Tab
    private val patternTableModel = DefaultTableModel(
        arrayOf("Base Token", "Pattern", "Occurrences", "Suggested Token"), 0
    )
    private val patternTable = JBTable(patternTableModel)
    private val patternSummaryLabel = JLabel("Press 'Scan Project' to detect patterns")
    private val patternIds = mutableListOf<String>()
    private var selectedPatternId: String? = null

    // Changes Tab
    private val changesTableModel = DefaultTableModel(
        arrayOf("File", "Changes", "Patterns"), 0
    )
    private val sharedTokensTableModel = DefaultTableModel(
        arrayOf("Token", "Value", "Usage"), 0
    )
    private val sharedTokensTable = JBTable(sharedTokensTableModel)
    private val sharedTokensList = mutableListOf<SharedToken>()
    private val changesTable = JBTable(changesTableModel)
    private val changesSummaryLabel = JLabel(" ")
    private val changesFilesList = mutableListOf<String>()
    private val changesBadgeLabel = JLabel("").apply {
        isOpaque = true
        background = badgeRed
        foreground = Color.WHITE
        font = Font("Segoe UI", Font.BOLD, 10)
        border = BorderFactory.createEmptyBorder(1, 6, 1, 6)
        isVisible = false
    }

    init {
        background = bgMain

        // 1. Top Toolbar
        val toolbar = JPanel(FlowLayout(FlowLayout.LEFT, 12, 8)).apply {
            background = bgDark
            border = BorderFactory.createEmptyBorder(2, 6, 2, 6)
        }
        val scanButton = createStyledButton("Scan Project", accentBlue, Color.WHITE)
        scanButton.addActionListener { onScanProject() }
        toolbar.add(scanButton)

        // Bridge Server Controls
        startBridgeButton.toolTipText = "Start Bridge Server (python server.py) and setup adb reverse"
        startBridgeButton.addActionListener { onStartBridge() }
        toolbar.add(startBridgeButton)

        stopBridgeButton.toolTipText = "Stop running Bridge Server"
        stopBridgeButton.addActionListener { onStopBridge() }
        toolbar.add(stopBridgeButton)

        toolbar.add(bridgeStatusLabel)

        // Sync Button
        syncButton.addActionListener { onTriggerSync() }
        syncButton.toolTipText = "Apply queued edits to files"
        toolbar.add(syncButton)

        // Queue Badge
        queueCountBadge.foreground = Color(0xE5, 0x51, 0x00)
        queueCountBadge.font = queueCountBadge.font.deriveFont(Font.BOLD)
        toolbar.add(queueCountBadge)

        // Status label
        syncStatusLabel.foreground = textMuted
        syncStatusLabel.font = Font("Segoe UI", Font.PLAIN, 12)
        toolbar.add(syncStatusLabel)

        val statusLabel = JLabel("Ready").apply {
            foreground = textMuted
            font = Font("Segoe UI", Font.PLAIN, 12)
        }
        toolbar.add(statusLabel)

        val settingsButton = createStyledButton("? Settings", btnGray, Color.WHITE)
        settingsButton.toolTipText = "Configure Python and Bridge paths"
        settingsButton.addActionListener {
            ShowSettingsUtil.getInstance().showSettingsDialog(project, ComposeBridgeConfigurable::class.java)
        }
        toolbar.add(settingsButton)

        // 2. Style Tables
        styleTable(scanTable)
        styleTable(impactTable)
        styleTable(splitTable)
        styleTable(patternTable)
        styleTable(changesTable)
        styleTable(sharedTokensTable)

        // 3. Scan Tab
        val scanPanel = JPanel(BorderLayout()).apply { background = bgMain }
        scanPanel.add(JBScrollPane(scanTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
        siblingsPanel.apply {
            background = bgDark
            border = BorderFactory.createEmptyBorder(6, 12, 6, 12)
        }
        siblingsTitleLabel.foreground = Color(0x93, 0xC5, 0xFD)
        siblingsTitleLabel.font = Font("Segoe UI", Font.BOLD, 12)
        scanPanel.add(siblingsPanel, BorderLayout.SOUTH)
        tabbedPane.addTab("Scan", scanPanel)

        // 4. Impact Tab
        val impactPanel = JPanel(BorderLayout()).apply { background = bgMain }
        val impactTop = JPanel(BorderLayout()).apply {
            background = bgDark
            border = BorderFactory.createEmptyBorder(6, 12, 6, 12)
        }
        impactTitleLabel.apply {
            foreground = textPrimary
            font = Font("Segoe UI", Font.BOLD, 12)
        }
        impactSummaryLabel.apply {
            foreground = textMuted
            font = Font("Segoe UI", Font.PLAIN, 12)
        }
        impactTop.add(impactTitleLabel, BorderLayout.NORTH)
        impactTop.add(impactSummaryLabel, BorderLayout.SOUTH)
        impactPanel.add(impactTop, BorderLayout.NORTH)
        impactPanel.add(JBScrollPane(impactTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
        tabbedPane.addTab("Impact", impactPanel)

        // 5. Split Tab
        val splitPanel = JPanel(BorderLayout()).apply { background = bgMain }
        splitSummaryLabel.apply {
            foreground = statusGreen
            font = Font("Segoe UI", Font.BOLD, 13)
            border = BorderFactory.createEmptyBorder(10, 16, 10, 16)
        }
        splitPanel.add(splitSummaryLabel, BorderLayout.NORTH)
        splitPanel.add(JBScrollPane(splitTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
        tabbedPane.addTab("Split", splitPanel)

        // 6. Patterns Tab
        val patternPanel = JPanel(BorderLayout()).apply { background = bgMain }
        patternSummaryLabel.apply {
            foreground = Color(0x60, 0xA5, 0xFA)
            font = Font("Segoe UI", Font.BOLD, 13)
            border = BorderFactory.createEmptyBorder(10, 16, 10, 16)
        }
        patternPanel.add(patternSummaryLabel, BorderLayout.NORTH)
        patternPanel.add(JBScrollPane(patternTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)

        val patternBottom = JPanel(FlowLayout(FlowLayout.LEFT, 12, 10)).apply {
            background = bgTabBar
            border = BorderFactory.createEmptyBorder(4, 8, 4, 8)
        }
        val replaceButton = createStyledButton("Replace Pattern", accentBlue, Color.WHITE)
        replaceButton.addActionListener { onReplacePattern() }
        patternBottom.add(replaceButton)

        val rollbackButton = createStyledButton("Rollback Pattern", btnRollback, Color.WHITE)
        rollbackButton.addActionListener { onRollbackPattern() }
        patternBottom.add(rollbackButton)

        val patternContainer = JPanel(BorderLayout()).apply { background = bgMain }
        patternContainer.add(patternPanel, BorderLayout.CENTER)
        patternContainer.add(patternBottom, BorderLayout.SOUTH)
        tabbedPane.addTab("Patterns", patternContainer)

        // 7. Changes Tab
        val changesPanel = JPanel(BorderLayout()).apply { background = bgMain }
        changesSummaryLabel.apply {
            foreground = statusGreen
            font = Font("Segoe UI", Font.BOLD, 13)
            border = BorderFactory.createEmptyBorder(10, 16, 8, 16)
        }
        changesPanel.add(changesSummaryLabel, BorderLayout.NORTH)

        val changesCenter = JPanel(GridLayout(2, 1, 0, 8)).apply { background = bgMain }

        val pendingFilesPanel = JPanel(BorderLayout()).apply { background = bgMain }
        pendingFilesPanel.add(JBScrollPane(changesTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
        val hintLabel = JLabel("Double-click any row to open the file in editor at the modified line").apply {
            foreground = textMuted
            font = Font("Segoe UI", Font.ITALIC, 11)
            border = BorderFactory.createEmptyBorder(4, 16, 4, 16)
        }
        pendingFilesPanel.add(hintLabel, BorderLayout.SOUTH)
        changesCenter.add(pendingFilesPanel)

        val sharedTokensPanel = JPanel(BorderLayout()).apply {
            background = bgMain
            border = BorderFactory.createMatteBorder(1, 0, 0, 0, bgHeader)
        }
        val sharedHeaderPanel = JPanel(BorderLayout()).apply {
            background = bgDark
            border = BorderFactory.createEmptyBorder(6, 16, 6, 16)
        }
        val sharedTitle = JLabel("🔗 Shared Tokens (Used in >1 place)").apply {
            foreground = accentBlue
            font = Font("Segoe UI", Font.BOLD, 12)
        }
        val splitSelectedBtn = createStyledButton("Split", btnGreen, Color.WHITE)
        splitSelectedBtn.addActionListener {
            val row = sharedTokensTable.selectedRow
            if (row != -1 && row < sharedTokensList.size) {
                val st = sharedTokensList[row]
                Messages.showInfoMessage(
                    "Token '${st.name}' is used in ${st.usage} places.\nUse Focus Mode in the mobile app to split it for a specific element.",
                    "Split Shared Token"
                )
            } else {
                Messages.showWarningDialog("Please select a shared token from the list first", "Split Shared Token")
            }
        }
        sharedHeaderPanel.add(sharedTitle, BorderLayout.WEST)
        sharedHeaderPanel.add(splitSelectedBtn, BorderLayout.EAST)
        sharedTokensPanel.add(sharedHeaderPanel, BorderLayout.NORTH)
        sharedTokensPanel.add(JBScrollPane(sharedTokensTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
        changesCenter.add(sharedTokensPanel)

        changesPanel.add(changesCenter, BorderLayout.CENTER)

        val changesBottom = JPanel(FlowLayout(FlowLayout.LEFT, 12, 10)).apply {
            background = bgTabBar
            border = BorderFactory.createEmptyBorder(4, 8, 4, 8)
        }
        val viewDiffBtn = createStyledButton("View Diff", accentBlue, Color.WHITE)
        viewDiffBtn.addActionListener { onViewDiffSelectedFile() }
        val approveAllBtn = createStyledButton("Approve All", btnGreen, Color.WHITE)
        approveAllBtn.addActionListener { onApproveAllFiles() }
        val rejectAllBtn = createStyledButton("Reject All", btnRed, Color.WHITE)
        rejectAllBtn.addActionListener { onRejectAllFiles() }
        val rejectForceBtn = createStyledButton("Force Reject", Color(0xFFB91C1C.toInt()), Color.WHITE)
        rejectForceBtn.addActionListener { onForceRejectAll() }
        val refreshBtn = createStyledButton("Refresh", btnGray, Color.WHITE)
        refreshBtn.addActionListener { refreshChanges() }

        changesBottom.add(viewDiffBtn)
        changesBottom.add(approveAllBtn)
        changesBottom.add(rejectAllBtn)
        changesBottom.add(rejectForceBtn)
        changesBottom.add(refreshBtn)
        changesPanel.add(changesBottom, BorderLayout.SOUTH)

        tabbedPane.addTab("Changes", changesPanel)

        // Custom Changes Tab Component with Red Badge
        val changesTabIndex = tabbedPane.indexOfTab("Changes")
        if (changesTabIndex != -1) {
            val tabTitlePanel = JPanel(FlowLayout(FlowLayout.LEFT, 6, 0)).apply {
                isOpaque = false
                add(JLabel("Changes").apply {
                    font = Font("Segoe UI", Font.BOLD, 12)
                    foreground = textPrimary
                })
                add(changesBadgeLabel)
            }
            tabbedPane.setTabComponentAt(changesTabIndex, tabTitlePanel)
        }

        // Double-click row in Changes -> open Diff preview
        changesTable.addMouseListener(object : java.awt.event.MouseAdapter() {
            override fun mouseClicked(e: java.awt.event.MouseEvent) {
                if (e.clickCount == 2) {
                    onViewDiffSelectedFile()
                }
            }
        })

        // Select row in Scan -> Impact
        scanTable.selectionModel.addListSelectionListener { event ->
            if (!event.valueIsAdjusting) {
                val selectedRow = scanTable.selectedRow
                if (selectedRow >= 0) {
                    val name = scanTableModel.getValueAt(selectedRow, 0) as? String
                    val type = scanTableModel.getValueAt(selectedRow, 3) as? String
                    if (type == "Token" && name != null && name != "(hardcoded)") {
                        onTokenSelected(name)
                    }
                }
            }
        }

        // Select row in Patterns Table
        patternTable.selectionModel.addListSelectionListener { event ->
            if (!event.valueIsAdjusting) {
                val row = patternTable.selectedRow
                if (row >= 0 && row < patternIds.size) {
                    selectedPatternId = patternIds[row]
                }
            }
        }

        add(toolbar, BorderLayout.NORTH)
        add(tabbedPane, BorderLayout.CENTER)

        // Check if bridge path is configured on launch
        SwingUtilities.invokeLater {
            val bridgePath = pythonRunner.getBridgePath()
            if (bridgePath.isBlank() || !File(bridgePath).exists()) {
                val res = Messages.showYesNoDialog(
                    project,
                    "ComposeBridge is not configured yet. Would you like to configure it now in Settings?",
                    "ComposeBridge Setup",
                    "Open Settings",
                    "Later",
                    Messages.getInformationIcon()
                )
                if (res == Messages.YES) {
                    ShowSettingsUtil.getInstance().showSettingsDialog(project, ComposeBridgeConfigurable::class.java)
                }
            }
        }

        // Clean up server on project disposal
        Disposer.register(project) {
            BridgeServerManager.stopServer()
        }

        // Sync UI with current server status
        updateBridgeStatusUi(BridgeServerManager.isRunning())

        // Auto-start Bridge server if enabled in settings
        val settings = ComposeBridgeSettings.getInstance(project)
        if (settings.state.autoStartBridge && !BridgeServerManager.isRunning()) {
            val bridgePath = pythonRunner.getBridgePath()
            if (bridgePath.isNotBlank() && File(bridgePath, "server.py").exists()) {
                bridgeStatusLabel.text = "🟡 Starting Bridge..."
                bridgeStatusLabel.foreground = Color(0xFB, 0xBF, 0x24)
                startBridgeButton.isEnabled = false
                Thread {
                    BridgeServerManager.startServer(
                        bridgePath = bridgePath,
                        pythonPath = settings.state.pythonPath,
                        projectRoot = project.basePath
                    ) { isRunning ->
                        SwingUtilities.invokeLater {
                            updateBridgeStatusUi(isRunning)
                        }
                    }
                    SwingUtilities.invokeLater {
                        startBridgeButton.isEnabled = true
                        updateBridgeStatusUi(BridgeServerManager.isRunning())
                    }
                }.start()
            }
        }
    }


    private fun updateBridgeStatusUi(running: Boolean) {
        if (running) {
            startBridgeButton.isVisible = false
            stopBridgeButton.isVisible = true
            bridgeStatusLabel.text = "🟢 Bridge Running"
            bridgeStatusLabel.foreground = statusGreen
        } else {
            startBridgeButton.isVisible = true
            stopBridgeButton.isVisible = false
            bridgeStatusLabel.text = "🔴 Bridge Stopped"
            bridgeStatusLabel.foreground = Color(0xF8, 0x71, 0x71)
        }
    }

    private fun onStartBridge() {
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
        bridgeStatusLabel.text = "🟡 Starting Bridge..."
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

    private fun onStopBridge() {
        stopBridgeButton.isEnabled = false
        bridgeStatusLabel.text = "🟡 Stopping..."
        bridgeStatusLabel.foreground = Color(0xFB, 0xBF, 0x24)

        Thread {
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

    private fun createStyledButton(text: String, bg: Color, fg: Color = Color.WHITE, radius: Int = 6): JButton {
        val btn = object : JButton(text) {
            override fun paintComponent(g: Graphics) {
                val g2 = g.create() as Graphics2D
                g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
                val fill = if (model.isPressed) bg.darker() else if (model.isRollover) bg.brighter() else bg
                g2.color = fill
                g2.fillRoundRect(0, 0, width, height, radius * 2, radius * 2)
                g2.dispose()
                super.paintComponent(g)
            }
        }
        btn.isContentAreaFilled = false
        btn.isFocusPainted = false
        btn.isBorderPainted = false
        btn.foreground = fg
        btn.font = Font("Segoe UI", Font.BOLD, 12)
        btn.cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
        btn.border = BorderFactory.createEmptyBorder(7, 16, 7, 16)
        return btn
    }

    private fun styleTable(table: JBTable) {
        table.rowHeight = 36
        table.setShowGrid(false)
        table.intercellSpacing = Dimension(0, 2)
        table.background = bgDark
        table.selectionBackground = bgSelected
        table.selectionForeground = Color.WHITE
        table.font = Font("Segoe UI", Font.PLAIN, 12)

        val header = table.tableHeader
        header.preferredSize = Dimension(header.preferredSize.width, 34)
        header.background = bgHeader
        header.foreground = textPrimary
        header.font = Font("Segoe UI", Font.BOLD, 12)

        table.setDefaultRenderer(Any::class.java, object : DefaultTableCellRenderer() {
            override fun getTableCellRendererComponent(
                t: JTable, value: Any?, isSelected: Boolean, hasFocus: Boolean, row: Int, col: Int
            ): Component {
                val comp = super.getTableCellRendererComponent(t, value, isSelected, hasFocus, row, col) as JLabel
                comp.border = BorderFactory.createEmptyBorder(0, 14, 0, 14)
                if (isSelected) {
                    comp.background = bgSelected
                    comp.foreground = Color.WHITE
                } else {
                    comp.background = if (row % 2 == 0) bgDark else bgRowAlt
                    comp.foreground = textPrimary
                }
                return comp
            }
        })
    }

    private fun extractJson(raw: String): String {
        val start = raw.indexOf('{')
        val end = raw.lastIndexOf('}')
        return if (start != -1 && end != -1 && end >= start) raw.substring(start, end + 1) else raw
    }

    private fun onTriggerSync() {
        syncButton.isEnabled = false
        syncStatusLabel.text = "Syncing..."
        syncStatusLabel.foreground = textMuted
        syncButton.text = "⏳ Syncing..."

        Thread {
            val json = pythonRunner.triggerUserSync()
            SwingUtilities.invokeLater {
                syncButton.isEnabled = true
                syncButton.text = "🔄 Sync Now"
                parseSyncResult(json)
            }
        }.start()
    }

    private fun parseSyncResult(json: String) {
        try {
            val cleanJson = extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")

            if (success) {
                val applied = root.get("applied")?.asInt ?: 0
                val skipped = root.get("skipped")?.asInt ?: 0
                val errors = root.get("errors")?.asInt ?: 0
                val status = root.get("status")?.asString ?: ""

                when (status) {
                    "refused" -> {
                        syncStatusLabel.text = "⚠️ Agent busy — cannot sync now"
                        syncStatusLabel.foreground = Color(0xE5, 0x51, 0x00)
                    }
                    "partial" -> {
                        syncStatusLabel.text = "⚠️ Applied $applied | Failed $skipped"
                        syncStatusLabel.foreground = Color(0xE5, 0x51, 0x00)
                    }
                    else -> {
                        if (applied == 0) {
                            syncStatusLabel.text = "ℹ️ No pending edits"
                            syncStatusLabel.foreground = textMuted
                        } else {
                            syncStatusLabel.text = "✅ Synced $applied edit(s)"
                            syncStatusLabel.foreground = statusGreen
                        }
                    }
                }

                queueCountBadge.text = " "

                val projectRoot = project.basePath
                if (projectRoot != null) {
                    refreshChanges()
                }
            } else {
                val error = root.get("error")?.asString ?: "Unknown error"
                syncStatusLabel.text = "❌ $error"
                syncStatusLabel.foreground = Color(0xC6, 0x28, 0x28)
            }
        } catch (e: Exception) {
            syncStatusLabel.text = "❌ Parse error: ${e.message}"
            syncStatusLabel.foreground = Color(0xC6, 0x28, 0x28)
        }
    }

    private fun updateQueueBadge(count: Int) {
        if (count > 0) {
            queueCountBadge.text = "📥 $count queued"
        } else {
            queueCountBadge.text = " "
        }
    }

    private fun refreshSyncStatus() {
        Thread {
            val json = pythonRunner.getSyncStatus()
            SwingUtilities.invokeLater {
                try {
                    val cleanJson = extractJson(json)
                    val root = gson.fromJson(cleanJson, JsonObject::class.java)
                    val queueCount = root.get("queue_count")?.asInt ?: 0
                    val agentBusy = root.get("agent_busy")?.asBoolean ?: false

                    updateQueueBadge(queueCount)

                    if (agentBusy) {
                        syncStatusLabel.text = "🤖 Agent busy"
                        syncStatusLabel.foreground = Color(0xE5, 0x51, 0x00)
                    } else if (queueCount > 0) {
                        syncStatusLabel.text = "Ready to sync"
                        syncStatusLabel.foreground = statusGreen
                    } else {
                        syncStatusLabel.text = " "
                    }
                } catch (e: Exception) {
                    // ignore if server not running
                }
            }
        }.start()
    }

    private fun onScanProject() {
        val bridgePath = pythonRunner.getBridgePath()
        if (bridgePath.isBlank() || !File(bridgePath).exists()) {
            val res = Messages.showYesNoDialog(
                project,
                "ComposeBridge path is not configured or not found. Please specify it in Settings.",
                "ComposeBridge Setup",
                "Open Settings",
                "Cancel",
                Messages.getWarningIcon()
            )
            if (res == Messages.YES) {
                ShowSettingsUtil.getInstance().showSettingsDialog(project, ComposeBridgeConfigurable::class.java)
            }
            return
        }
        val projectRoot = project.basePath ?: return
        scanTableModel.rowCount = 0
        scanTableModel.addRow(arrayOf("Scanning...", "", "", ""))

        Thread {
            val json = pythonRunner.runScanner(projectRoot)
            SwingUtilities.invokeLater {
                scanTableModel.rowCount = 0
                parseAndFillScanResults(json)
                refreshSplitSuggestions(projectRoot)
                refreshPatterns(projectRoot)
                refreshChanges()
                refreshSyncStatus()
            }
        }.start()
    }

    private fun onTokenSelected(tokenName: String) {
        impactTitleLabel.text = "Impact: $tokenName"
        impactSummaryLabel.text = "Loading..."
        impactTableModel.rowCount = 0

        Thread {
            val json = pythonRunner.getTokenImpact(tokenName)
            SwingUtilities.invokeLater {
                parseAndFillImpactResults(json, tokenName)
            }
        }.start()

        Thread {
            val siblingsJson = pythonRunner.getTokenSiblings(tokenName)
            SwingUtilities.invokeLater {
                try {
                    val cleanJson = extractJson(siblingsJson)
                    val json = gson.fromJson(cleanJson, JsonObject::class.java)
                    val siblings = json.getAsJsonArray("siblings")
                    siblingsPanel.removeAll()
                    if (siblings != null && siblings.size() > 0) {
                        siblingsPanel.add(siblingsTitleLabel)
                        for (i in 0 until siblings.size()) {
                            val sibling = siblings.get(i).asString
                            val linkButton = JButton(sibling)
                            linkButton.isBorderPainted = false
                            linkButton.isContentAreaFilled = false
                            linkButton.foreground = Color(0x60, 0xA5, 0xFA)
                            linkButton.cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
                            linkButton.font = Font("Segoe UI", Font.BOLD, 12)
                            linkButton.addActionListener {
                                openTokenDefinition(sibling)
                            }
                            siblingsPanel.add(linkButton)
                            if (i < siblings.size() - 1) {
                                siblingsPanel.add(JLabel(",").apply { foreground = textMuted })
                            }
                        }
                    }
                    siblingsPanel.revalidate()
                    siblingsPanel.repaint()
                } catch (e: Exception) {
                    siblingsPanel.removeAll()
                    siblingsPanel.revalidate()
                    siblingsPanel.repaint()
                }
            }
        }.start()
    }

    private fun openTokenDefinition(tokenName: String) {
        val projectRoot = project.basePath ?: return
        var foundFile: com.intellij.openapi.vfs.VirtualFile? = null
        var foundLine = 0

        val rootVFile = com.intellij.openapi.vfs.LocalFileSystem.getInstance().findFileByPath(projectRoot) ?: return
        com.intellij.openapi.vfs.VfsUtil.processFilesRecursively(rootVFile) { vFile ->
            if (vFile == null || vFile.isDirectory) return@processFilesRecursively true
            if (!vFile.name.endsWith(".kt")) return@processFilesRecursively true
            val path = vFile.path
            if (path.contains("/build/") || path.contains("\\build\\")) {
                return@processFilesRecursively true
            }
            try {
                val content = String(vFile.contentsToByteArray(), Charsets.UTF_8)
                val regex = Regex("""val\s+${Regex.escape(tokenName)}\s*[:=]""")
                val match = regex.find(content)
                if (match != null) {
                    foundLine = content.substring(0, match.range.first).count { it == '\n' }
                    foundFile = vFile
                    return@processFilesRecursively false
                }
            } catch (e: Exception) {
                // ignore
            }
            true
        }

        val vFile = foundFile ?: run {
            Messages.showWarningDialog(
                "Could not find token '$tokenName'",
                "ComposeBridge"
            )
            return
        }

        val lineIndex = if (foundLine > 0) foundLine else 0
        com.intellij.openapi.fileEditor.OpenFileDescriptor(
            project, vFile, lineIndex, 0
        ).navigate(true)
    }

    private fun parseAndFillScanResults(json: String) {
        try {
            val cleanJson = extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val registered = root.getAsJsonArray("registered_tokens")
            val hardcoded = root.getAsJsonArray("hardcoded_values")

            if (registered != null) {
                for (elem in registered) {
                    val obj = elem.asJsonObject
                    scanTableModel.addRow(arrayOf(
                        obj.get("name")?.asString ?: "",
                        obj.get("value")?.asString ?: "",
                        obj.get("file")?.asString ?: "",
                        "Token"
                    ))
                }
            }

            if (hardcoded != null) {
                for (elem in hardcoded) {
                    val obj = elem.asJsonObject
                    scanTableModel.addRow(arrayOf(
                        "(hardcoded)",
                        obj.get("value")?.asString ?: "",
                        "${obj.get("file")?.asString ?: ""}:${obj.get("line")?.asInt ?: 0}",
                        obj.get("kind")?.asString ?: ""
                    ))
                }
            }
        } catch (e: Exception) {
            scanTableModel.addRow(arrayOf("Error", e.message ?: "", "", ""))
        }
    }

        private fun parseAndFillImpactResults(json: String, tokenName: String) {
        try {
            val cleanJson = extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")

            if (!success) {
                val error = root.get("error")?.asString ?: "Unknown error"
                impactSummaryLabel.text = "Error: $error"
                return
            }

            val total = root.get("total_impact")?.asInt ?: 0
            val affectedArr = if (root.has("affected_composables") && root.get("affected_composables").isJsonArray) {
                root.getAsJsonArray("affected_composables")
            } else null

            val affectedCount = affectedArr?.size() ?: 0
            val affectedList = if (affectedArr != null) {
                val list = mutableListOf<String>()
                for (elem in affectedArr) {
                    list.add(elem.asString)
                }
                list.take(10).joinToString(", ") + (if (list.size > 10) "..." else "")
            } else ""

            impactTitleLabel.text = "Impact: $tokenName"
            impactSummaryLabel.text = "Total: $total usage(s) across $affectedCount @Composable(s) ($affectedList)"

            impactTableModel.rowCount = 0

            val usages = if (root.has("usages") && root.get("usages").isJsonArray) {
                root.getAsJsonArray("usages")
            } else null

            if (usages != null) {
                for (elem in usages) {
                    try {
                        val obj = elem.asJsonObject
                        val file = obj.get("file")?.asString ?: "?"
                        val line = obj.get("line")?.asInt?.toString() ?: "0"
                        val content = obj.get("line_content")?.asString ?: ""
                        val composable = obj.get("enclosing_composable")?.asString ?: "?"
                        
                        impactTableModel.addRow(arrayOf(file, line, content, composable))
                    } catch (e: Exception) {
                        // ignore row
                    }
                }
            }

            if (impactTableModel.rowCount == 0) {
                impactTableModel.addRow(arrayOf("No usages", "", "", ""))
            }
        } catch (e: Exception) {
            impactSummaryLabel.text = "Error parsing: ${e.message}"
        }
    }

    private fun refreshSplitSuggestions(projectRoot: String) {
        splitSummaryLabel.text = "Analyzing token usage..."
        splitTableModel.rowCount = 0

        Thread {
            val json = pythonRunner.getSuggestions(projectRoot)
            SwingUtilities.invokeLater {
                parseAndFillSplitResults(json)
            }
        }.start()
    }

    private fun parseAndFillSplitResults(json: String) {
        try {
            val cleanJson = extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val count = root.get("count")?.asInt ?: 0
            if (count == 0) {
                splitSummaryLabel.text = "No splits needed — all tokens use single context"
                return
            }
            splitSummaryLabel.text = "Found $count token(s) used in multiple contexts:"

            val suggestions = root.getAsJsonArray("suggestions")
            if (suggestions != null) {
                for (elem in suggestions) {
                    val obj = elem.asJsonObject
                    val tokenName = obj.get("token_name")?.asString ?: ""
                    val tokenValue = obj.get("token_value")?.asString ?: ""

                    val contextsObj = obj.getAsJsonObject("contexts")
                    val contextsStr = contextsObj?.entrySet()?.joinToString(", ") { "${it.key}: ${it.value}" } ?: ""

                    val suggestedArr = obj.getAsJsonArray("suggested_tokens")
                    val suggestedStr = suggestedArr?.joinToString(", ") {
                        val s = it.asJsonObject
                        "${s.get("name")?.asString} (${s.get("context")?.asString})"
                    } ?: ""

                    splitTableModel.addRow(arrayOf(
                        tokenName,
                        tokenValue,
                        contextsStr,
                        suggestedStr
                    ))
                }
            }
        } catch (e: Exception) {
            splitSummaryLabel.text = "Error: ${e.message}"
        }
    }

    private fun refreshPatterns(projectRoot: String) {
        patternSummaryLabel.text = "Detecting patterns..."
        patternTableModel.rowCount = 0
        patternIds.clear()
        selectedPatternId = null

        Thread {
            val json = pythonRunner.detectPatterns()
            SwingUtilities.invokeLater {
                parseAndFillPatterns(json)
            }
        }.start()
    }

        private fun parseAndFillPatterns(json: String) {
        try {
            val cleanJson = extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")
            if (!success) {
                patternSummaryLabel.text = "Error: ${root.get("error")?.asString}"
                return
            }
            val count = root.get("count")?.asInt ?: 0
            if (count == 0) {
                patternSummaryLabel.text = "No repeated patterns detected"
                return
            }
            patternSummaryLabel.text = "Detected $count conditional pattern(s):"

            patternTableModel.rowCount = 0
            patternIds.clear()

            val patterns = if (root.has("patterns") && root.get("patterns").isJsonArray) {
                root.getAsJsonArray("patterns")
            } else null

            if (patterns != null) {
                for (elem in patterns) {
                    val obj = elem.asJsonObject
                    val patternId = obj.get("pattern_id")?.asString ?: ""
                    val suggested = obj.get("suggested_token_name")?.asString ?: "?"
                    val suggestedValue = obj.get("suggested_token_value")?.asString ?: ""

                    // Base token extraction
                    val baseToken = if (patternId.startsWith("dark_")) {
                        val parts = patternId.substring(5).split("_", limit = 2)
                        if (parts.isNotEmpty()) parts[0] else "?"
                    } else {
                        suggested.removeSuffix("Dark")
                    }

                    // occurrences count
                    var occ = if (obj.has("occurrences")) obj.get("occurrences")?.asInt else null
                    if (occ == null || occ == 0) {
                        val details = if (obj.has("details") && obj.get("details").isJsonArray) obj.getAsJsonArray("details") else null
                        occ = details?.size() ?: 0
                    }

                    val suggestedStr = if (suggestedValue.isNotEmpty()) {
                        "$suggested ($suggestedValue)"
                    } else {
                        suggested
                    }

                    patternIds.add(patternId)

                    patternTableModel.addRow(arrayOf(
                        baseToken,
                        patternId,
                        "$occ",
                        suggestedStr
                    ))
                }
            }
        } catch (e: Exception) {
            patternSummaryLabel.text = "Error: ${e.message}"
        }
    }

    private fun onReplacePattern() {
        val patternId = selectedPatternId ?: run {
            Messages.showWarningDialog("Please select a pattern first", "ComposeBridge")
            return
        }

        val selectedRow = patternTable.selectedRow
        if (selectedRow < 0) return

        val pattern = patternTableModel.getValueAt(selectedRow, 1) as? String ?: "?"
        val occ = patternTableModel.getValueAt(selectedRow, 2) as? String ?: "?"
        val suggested = patternTableModel.getValueAt(selectedRow, 3) as? String ?: "?"

        val message = """
            Pattern: $pattern
            Occurrences: $occ

            This will:
            1. Create token: $suggested
            2. Replace all $occ occurrences

            ⚠️ Make sure you have committed your changes to git first.

            Continue?
        """.trimIndent()

        val choice = Messages.showYesNoDialog(
            message,
            "ComposeBridge — Replace Pattern",
            Messages.getWarningIcon()
        )

        if (choice != Messages.YES) return

        Thread {
            val json = pythonRunner.replacePattern(patternId)
            SwingUtilities.invokeLater {
                parseAndShowReplaceResult(json)
            }
        }.start()
    }

    private fun parseAndShowReplaceResult(json: String) {
        try {
            val cleanJson = extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")

            if (success) {
                val token = root.get("token_name")?.asString ?: "?"
                val count = root.get("replacements_count")?.asInt ?: 0
                Messages.showInfoMessage(
                    "Token '$token' created.\n$count replacements made.",
                    "ComposeBridge"
                )
                val projectRoot = project.basePath ?: return
                refreshPatterns(projectRoot)
                refreshChanges()
                refreshSyncStatus()
            } else {
                val token = root.get("suggested_token")?.asString ?: root.get("token_name")?.asString ?: "?"
                val error = root.get("error")?.asString ?: "Unknown"
                Messages.showErrorDialog(
                    "Pattern replacement failed.\n\nToken: $token\nError: $error",
                    "ComposeBridge"
                )
            }
        } catch (e: Exception) {
            Messages.showErrorDialog("Error: ${e.message}", "ComposeBridge")
        }
    }

    private fun openFileAtLine(filePath: String, line: Int) {
        val projectRoot = project.basePath ?: return
        val targetName = java.io.File(filePath).name
        var foundFile: com.intellij.openapi.vfs.VirtualFile? = null

        val fullPath = if (java.io.File(filePath).isAbsolute) filePath else "$projectRoot/$filePath"
        val directVFile = com.intellij.openapi.vfs.LocalFileSystem.getInstance().findFileByPath(fullPath.replace("\\", "/"))
        if (directVFile != null && directVFile.exists()) {
            foundFile = directVFile
        } else {
            val rootVFile = com.intellij.openapi.vfs.LocalFileSystem.getInstance().findFileByPath(projectRoot) ?: return
            com.intellij.openapi.vfs.VfsUtil.processFilesRecursively(rootVFile) { vFile ->
                if (vFile == null || vFile.isDirectory) return@processFilesRecursively true
                val path = vFile.path
                if (path.contains("/build/") || path.contains("\\build\\")) return@processFilesRecursively true
                if (vFile.name == targetName) {
                    foundFile = vFile
                    return@processFilesRecursively false
                }
                true
            }
        }

        val vFile = foundFile ?: run {
            Messages.showWarningDialog("Could not find file '$filePath'", "ComposeBridge")
            return
        }

        val lineIndex = if (line > 0) line - 1 else 0
        com.intellij.openapi.fileEditor.OpenFileDescriptor(
            project, vFile, lineIndex, 0
        ).navigate(true)
    }

    private fun refreshChanges() {
        changesSummaryLabel.text = "Loading modified files..."
        changesTableModel.rowCount = 0
        changesFilesList.clear()

        Thread {
            val json = pythonRunner.listModifiedFiles()
            SwingUtilities.invokeLater { parseAndFillChanges(json) }
        }.start()

        refreshSharedTokens()
    }

    private fun refreshSharedTokens() {
        Thread {
            val json = pythonRunner.listTokens(project.basePath)
            SwingUtilities.invokeLater {
                try {
                    val root = gson.fromJson(extractJson(json), JsonObject::class.java)
                    val tokens = root.getAsJsonArray("registered_tokens")
                    
                    sharedTokensList.clear()
                    tokens?.forEach { elem ->
                        val obj = elem.asJsonObject
                        val name = obj.get("name")?.asString ?: return@forEach
                        val value = obj.get("value")?.asString ?: ""
                        val usage = obj.get("usage_count")?.asInt ?: 0
                        
                        if (usage > 1) {
                            sharedTokensList.add(SharedToken(name, value, usage))
                        }
                    }
                    
                    sharedTokensTableModel.rowCount = 0
                    sharedTokensList.forEach { st ->
                        sharedTokensTableModel.addRow(arrayOf(
                            st.name, st.value, "${st.usage} places"
                        ))
                    }
                } catch (e: Exception) {
                    // ignore
                }
            }
        }.start()
    }

    private fun parseAndFillChanges(json: String) {
        try {
            val cleanJson = extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")
            if (!success) {
                changesSummaryLabel.text = "Error: ${root.get("error")?.asString}"
                changesBadgeLabel.isVisible = false
                return
            }
            val count = root.get("count")?.asInt ?: 0
            if (count == 0) {
                changesSummaryLabel.text = "No pending file changes on disk"
                changesBadgeLabel.isVisible = false
                return
            }
            changesSummaryLabel.text = "$count file(s) modified on disk — Review to Approve or Revert"
            changesBadgeLabel.text = "$count"
            changesBadgeLabel.isVisible = true

            if (root.has("files") && root.get("files").isJsonArray) {
                val files = root.getAsJsonArray("files")
                for (elem in files) {
                    val obj = elem.asJsonObject
                    val file = if (obj.has("file") && !obj.get("file").isJsonNull) obj.get("file").asString else "?"
                    val changeCount = if (obj.has("change_count")) obj.get("change_count").asInt else 0
                    val pArr = if (obj.has("pattern_ids")) obj.getAsJsonArray("pattern_ids") else null
                    val patterns = if (pArr != null) {
                        val pList = mutableListOf<String>()
                        for (p in pArr) {
                            pList.add(p.asString)
                        }
                        pList.joinToString(", ")
                    } else ""
                    changesFilesList.add(file)
                    val changesStr = if (changeCount == 1) "1 change" else "$changeCount changes"
                    changesTableModel.addRow(arrayOf(file, changesStr, patterns))
                }
            }
        } catch (e: Exception) {
            changesSummaryLabel.text = "Error: ${e.message}"
            changesBadgeLabel.isVisible = false
        }
    }

    private fun onViewDiffSelectedFile() {
        val row = changesTable.selectedRow
        if (row < 0 || row >= changesFilesList.size) {
            Messages.showWarningDialog("Please select a file to view diff", "ComposeBridge")
            return
        }
        val file = changesFilesList[row]
        Thread {
            val json = pythonRunner.getFileDiff(file)
            SwingUtilities.invokeLater {
                try {
                    val cleanJson = extractJson(json)
                    val root = gson.fromJson(cleanJson, JsonObject::class.java)
                    if (root.get("success")?.asBoolean == true) {
                        val originalText = root.get("original_content")?.asString ?: ""
                        val currentText = root.get("current_content")?.asString ?: ""
                        val fileName = java.io.File(file).name

                        val contentFactory = com.intellij.diff.DiffContentFactory.getInstance()
                        val originalContent = contentFactory.create(originalText)
                        val currentContent = contentFactory.create(currentText)

                        val request = com.intellij.diff.requests.SimpleDiffRequest(
                            "Diff: $fileName (Before vs Current)",
                            originalContent,
                            currentContent,
                            "Original (Before Pattern)",
                            "Current on Disk (Modified)"
                        )
                        com.intellij.diff.DiffManager.getInstance().showDiff(project, request)
                    } else {
                        val err = root.get("error")?.asString ?: "Could not load diff"
                        Messages.showErrorDialog(err, "ComposeBridge - Diff Error")
                    }
                } catch (e: Exception) {
                    Messages.showErrorDialog("Error loading diff: ${e.message}", "ComposeBridge")
                }
            }
        }.start()
    }

    private fun onApproveAllFiles() {
        val choice = Messages.showYesNoDialog(
            "Approve all changes?\n\nThis will mark all changes as accepted and clear the journal.",
            "ComposeBridge — Approve All",
            Messages.getQuestionIcon()
        )
        if (choice != Messages.YES) return
        Thread {
            pythonRunner.approveAllFiles()
            SwingUtilities.invokeLater { refreshChanges() }
        }.start()
    }

    private fun onForceRejectAll() {
        val choice = Messages.showYesNoDialog(
            "Force revert all changes? This will clear the journal even if some file reverts fail!",
            "ComposeBridge — Force Reject All",
            Messages.getWarningIcon()
        )
        if (choice != Messages.YES) return
        Thread {
            pythonRunner.rejectAllFilesForce()
            SwingUtilities.invokeLater {
                refreshChanges()
                val projectRoot = project.basePath ?: return@invokeLater
                refreshPatterns(projectRoot)
            }
        }.start()
    }

    private fun onRejectAllFiles() {
        val choice = Messages.showYesNoDialog(
            "Revert all changes? This cannot be undone!",
            "ComposeBridge — Reject All",
            Messages.getWarningIcon()
        )
        if (choice != Messages.YES) return
        Thread {
            pythonRunner.rejectAllFiles()
            SwingUtilities.invokeLater {
                refreshChanges()
                val projectRoot = project.basePath ?: return@invokeLater
                refreshPatterns(projectRoot)
            }
        }.start()
    }

    private fun onRollbackPattern() {
        val patternId = selectedPatternId ?: run {
            Messages.showWarningDialog("Please select a pattern first", "ComposeBridge")
            return
        }

        val choice = Messages.showYesNoDialog(
            "Rollback all changes for this pattern?\n\n" +
            "This will reverse every file modified by this pattern.",
            "ComposeBridge — Rollback Pattern",
            Messages.getWarningIcon()
        )

        if (choice != Messages.YES) return

        Thread {
            val json = pythonRunner.rollbackPattern(patternId)
            SwingUtilities.invokeLater {
                try {
                    val cleanJson = extractJson(json)
                    val root = gson.fromJson(cleanJson, JsonObject::class.java)
                    val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")

                    if (success) {
                        val count = root.get("reverted_count")?.asInt ?: 0
                        val errors = root.get("error_count")?.asInt ?: 0
                        Messages.showInfoMessage(
                            "Rollback complete.\nReverted: $count files\nErrors: $errors",
                            "ComposeBridge"
                        )
                        val projectRoot = project.basePath ?: return@invokeLater
                        refreshPatterns(projectRoot)
                        refreshChanges()
                    } else {
                        val error = root.get("error")?.asString ?: "Unknown"
                        Messages.showErrorDialog(error, "ComposeBridge")
                    }
                } catch (e: Exception) {
                    Messages.showErrorDialog("Error: ${e.message}", "ComposeBridge")
                }
            }
        }.start()
    }
}
