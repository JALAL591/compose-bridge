package com.composebridge.plugin.toolwindow

import com.composebridge.plugin.services.BridgeServerManager
import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.settings.ComposeBridgeConfigurable
import com.composebridge.plugin.settings.ComposeBridgeSettings
import com.composebridge.plugin.toolwindow.tabs.*
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.intellij.openapi.Disposable
import com.intellij.openapi.options.ShowSettingsUtil
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.util.Disposer
import com.intellij.openapi.vfs.VirtualFileManager
import com.intellij.openapi.vfs.newvfs.BulkFileListener
import com.intellij.openapi.vfs.newvfs.events.VFileEvent
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import java.awt.BorderLayout
import java.awt.Color
import java.awt.FlowLayout
import java.awt.Font
import java.io.File
import javax.swing.*

class ComposeBridgeToolWindowFactory : ToolWindowFactory, DumbAware {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = ComposeBridgePanel(project, toolWindow.disposable)
        val content = ContentFactory.getInstance().createContent(panel, "", false)
        toolWindow.contentManager.addContent(content)
        Disposer.register(toolWindow.disposable, panel)
    }

    override fun shouldBeAvailable(project: Project): Boolean = true
}

class ComposeBridgePanel(
    private val project: Project,
    private val parentDisposable: Disposable = project
) : JPanel(BorderLayout()), Disposable {

    private val pythonRunner = PythonRunner(project)

    private val changesBadgeLabel = JLabel("").apply {
        isOpaque = true
        background = BridgeColors.badgeRed
        foreground = Color.WHITE
        font = Font("Segoe UI", Font.BOLD, 10)
        border = BorderFactory.createEmptyBorder(1, 6, 1, 6)
        isVisible = false
    }

    private val changesDebounceTimer = Timer(600) {
        changesPanel.refreshChanges()
    }.apply { isRepeats = false }

    private val pendingSyntaxCheckFiles = mutableSetOf<String>()
    private val syntaxDebounceTimer = Timer(1200) {
        val filesToCheck = synchronized(pendingSyntaxCheckFiles) {
            val list = pendingSyntaxCheckFiles.toList()
            pendingSyntaxCheckFiles.clear()
            list
        }
        if (filesToCheck.isNotEmpty()) {
            Thread {
                for (fPath in filesToCheck) {
                    scannerPanel.runSingleFileSyntaxCheck(fPath)
                }
            }.start()
        }
    }.apply { isRepeats = false }

    // Tab Panels
    private val impactPanel: ImpactTabPanel
    private val splitPanel: SplitTabPanel
    private val patternsPanel: PatternsTabPanel
    private val changesPanel: ChangesTabPanel
    private val scannerPanel: ScannerTabPanel
    private val discoveryPanel: DiscoveryTabPanel
    private val diagnosticsPanel: DiagnosticsTabPanel
    private val helpPanel: HelpTabPanel
    private val headerPanel: ServerHeaderPanel

    private val tabbedPane = JTabbedPane()

    init {
        background = BridgeColors.bgMain

        impactPanel = ImpactTabPanel(project, pythonRunner) { file, line ->
            BridgeUiUtils.openFileAtLine(project, file, line)
        }

        splitPanel = SplitTabPanel(project, pythonRunner)

        patternsPanel = PatternsTabPanel(project, pythonRunner) {
            changesPanel.refreshChanges()
            headerPanel.refreshSyncStatus()
        }

        changesPanel = ChangesTabPanel(
            project,
            pythonRunner,
            openFileAtLine = { file, line -> BridgeUiUtils.openFileAtLine(project, file, line) },
            onPatternsRefreshNeeded = {
                project.basePath?.let { patternsPanel.refreshPatterns(it) }
            },
            changesBadgeLabel = changesBadgeLabel
        )

        discoveryPanel = DiscoveryTabPanel(project, pythonRunner) { file, line ->
            BridgeUiUtils.openFileAtLine(project, file, line)
        }

        diagnosticsPanel = DiagnosticsTabPanel(project) { file, line ->
            BridgeUiUtils.openFileAtLine(project, file, line)
        }

        helpPanel = HelpTabPanel(project)

        scannerPanel = ScannerTabPanel(
            project,
            pythonRunner,
            openFileAtLine = { file, line -> BridgeUiUtils.openFileAtLine(project, file, line) },
            onTokenSelectedCallback = { tokenName -> impactPanel.loadImpact(tokenName) },
            onScanFinishedCallbacks = { projectRoot ->
                splitPanel.refreshSplitSuggestions(projectRoot)
                patternsPanel.refreshPatterns(projectRoot)
                changesPanel.refreshChanges()
                headerPanel.refreshSyncStatus()
                discoveryPanel.refreshScatter()
            }
        )

        headerPanel = ServerHeaderPanel(
            project,
            pythonRunner,
            onScanProjectClicked = { scannerPanel.onScanProject() },
            onRefreshChangesNeeded = { changesPanel.refreshChanges() }
        )

        // Assemble tabs
        tabbedPane.addTab("Scan", scannerPanel)
        tabbedPane.addTab("Discovery", discoveryPanel)
        tabbedPane.addTab("Impact", impactPanel)
        tabbedPane.addTab("Split", splitPanel)
        tabbedPane.addTab("Patterns", patternsPanel)
        tabbedPane.addTab("Changes", changesPanel)
        tabbedPane.addTab("Diagnostics", diagnosticsPanel)
        tabbedPane.addTab("Help", helpPanel)

        // Custom Changes Tab Component with Red Badge
        val changesTabIndex = tabbedPane.indexOfTab("Changes")
        if (changesTabIndex != -1) {
            val tabTitlePanel = JPanel(FlowLayout(FlowLayout.LEFT, 6, 0)).apply {
                isOpaque = false
                add(JLabel("Changes").apply {
                    font = Font("Segoe UI", Font.BOLD, 12)
                    foreground = BridgeColors.textPrimary
                })
                add(changesBadgeLabel)
            }
            tabbedPane.setTabComponentAt(changesTabIndex, tabTitlePanel)
        }

        // Auto-refresh Changes and Discovery tabs whenever user selects them
        tabbedPane.addChangeListener {
            val cIdx = tabbedPane.indexOfTab("Changes")
            if (cIdx != -1 && tabbedPane.selectedIndex == cIdx) {
                changesPanel.refreshChanges()
            }
            val dIdx = tabbedPane.indexOfTab("Discovery")
            if (dIdx != -1 && tabbedPane.selectedIndex == dIdx) {
                discoveryPanel.refreshScatter()
            }

        }

        // Virtual File Watcher & Document Listener for real-time changes
        val docListener = object : com.intellij.openapi.editor.event.DocumentListener {
            override fun documentChanged(event: com.intellij.openapi.editor.event.DocumentEvent) {
                val fdm = com.intellij.openapi.fileEditor.FileDocumentManager.getInstance()
                val vFile = fdm.getFile(event.document) ?: return
                if (vFile.extension != "kt") return
                val pRoot = project.basePath ?: return
                if (!vFile.path.startsWith(pRoot)) return
                if (vFile.path.contains("/build/") || vFile.path.contains("\\build\\")) return
                synchronized(pendingSyntaxCheckFiles) {
                    pendingSyntaxCheckFiles.add(vFile.path)
                }
                syntaxDebounceTimer.restart()
            }
        }
        com.intellij.openapi.editor.EditorFactory.getInstance().eventMulticaster.addDocumentListener(docListener, parentDisposable)

        val connection = project.messageBus.connect(parentDisposable)
        connection.subscribe(VirtualFileManager.VFS_CHANGES, object : BulkFileListener {
            override fun after(events: List<VFileEvent>) {
                var shouldRefresh = false
                for (event in events) {
                    val path = (event.path ?: "").replace('\\', '/')
                    val file = event.file
                    val name = file?.name ?: File(path).name

                    if (name.endsWith(".kt")) {
                        if (!path.contains("/build/") && !path.contains("\\build\\")) {
                            synchronized(pendingSyntaxCheckFiles) {
                                pendingSyntaxCheckFiles.add(path)
                            }
                            syntaxDebounceTimer.restart()
                        }
                        val bakFile = File(path + ".bridge.bak")
                        val parentPath = file?.parent?.path ?: File(path).parent
                        val altBak = if (parentPath != null) File(parentPath, "$name.bridge.bak") else null
                        if (bakFile.exists() || (altBak != null && altBak.exists())) {
                            shouldRefresh = true
                            break
                        }
                        val bPath = project.basePath ?: ""
                        val journalFile = File(bPath, ".composebridge-state/pattern_journal.jsonl")
                        val pendingFile = File(bPath, ".composebridge-state/pending_edits.json")
                        val rootPending = File(bPath, "pending_edits.json")
                        if (journalFile.exists() && journalFile.readText().contains(name)) {
                            shouldRefresh = true
                            break
                        }
                        if (pendingFile.exists() && pendingFile.readText().contains(name)) {
                            shouldRefresh = true
                            break
                        }
                        if (rootPending.exists() && rootPending.readText().contains(name)) {
                            shouldRefresh = true
                            break
                        }
                    } else if (name.endsWith(".bridge.bak") ||
                               name == "pattern_journal.jsonl" ||
                               name == "pending_edits.json" ||
                               name == ".composebridge-journal.json") {
                        shouldRefresh = true
                        break
                    }
                }

                if (shouldRefresh) {
                    changesDebounceTimer.restart()
                }
            }
        })

        add(headerPanel, BorderLayout.NORTH)
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

        // Auto-start Bridge server if enabled in settings
        val settings = ComposeBridgeSettings.getInstance(project)
        if (settings.state.autoStartBridge && !BridgeServerManager.isRunning()) {
            val bridgePath = pythonRunner.getBridgePath()
            if (bridgePath.isNotBlank() && File(bridgePath, "server.py").exists()) {
                headerPanel.bridgeStatusLabel.text = "Starting Bridge..."
                headerPanel.bridgeStatusLabel.foreground = Color(0xFB, 0xBF, 0x24)
                headerPanel.startBridgeButton.isEnabled = false
                Thread {
                    BridgeServerManager.startServer(
                        bridgePath = bridgePath,
                        pythonPath = settings.state.pythonPath,
                        projectRoot = project.basePath
                    ) { isRunning ->
                        SwingUtilities.invokeLater {
                            headerPanel.updateBridgeStatusUi(isRunning)
                        }
                    }
                    SwingUtilities.invokeLater {
                        headerPanel.startBridgeButton.isEnabled = true
                        headerPanel.updateBridgeStatusUi(BridgeServerManager.isRunning())
                    }
                }.start()
            }
        }
    }

    fun updateBridgeStatus(running: Boolean) {
        headerPanel.updateBridgeStatusUi(running)
    }

    override fun dispose() {
        changesDebounceTimer.stop()
        syntaxDebounceTimer.stop()
    }
}
