package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.IdeDiagnosticsService
import com.composebridge.plugin.services.ProjectDiagnosticsScanner
import com.composebridge.plugin.state.DiagnosticsState
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.treeStructure.treetable.TreeTable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import java.awt.*
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent
import javax.swing.*
import javax.swing.table.DefaultTableCellRenderer
import javax.swing.tree.TreePath

/**
 * Visual tab panel for real-time IDE diagnostics with collapsible TreeTable & Inspection Filtering.
 * Groups findings hierarchically by source file, with total issues shown per file row.
 * Clicking a file row expands its issues downwards, clicking an issue navigates directly
 * to that line. Scan results and filter preferences are permanently preserved across sessions.
 */
class DiagnosticsTabPanel(
    private val project: Project,
    private val openFileAtLine: (String, Int) -> Unit = { f, l -> BridgeUiUtils.openFileAtLine(project, f, l) }
) : JPanel(BorderLayout()) {

    private val scope = CoroutineScope(Dispatchers.Default)
    private var currentScanJob: Job? = null

    data class FileScanRecord(
        val fileName: String,
        val relativePath: String,
        val items: List<IdeDiagnosticsService.DiagnosticItem>
    )

    // Master store for all raw scan findings before filtering
    private val allResultsByFile = LinkedHashMap<String, FileScanRecord>()

    private val summaryLabel = JLabel("Ready. Click Scan Project to inspect diagnostics.").apply {
        foreground = BridgeColors.textMuted
        font = Font("Segoe UI", Font.BOLD, 12)
        border = BorderFactory.createEmptyBorder(8, 12, 8, 12)
    }

    private val includeWarningsCheck = JCheckBox("Include Warnings", true).apply {
        isOpaque = false
        foreground = BridgeColors.textPrimary
        font = Font("Segoe UI", Font.PLAIN, 11)
        cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
    }

    private val refreshButton = BridgeUiUtils.createStyledButton("Refresh File", BridgeColors.accentBlue).apply {
        addActionListener { refreshDiagnostics() }
    }

    private val scanProjectButton = BridgeUiUtils.createStyledButton("Scan Project", BridgeColors.btnGreen).apply {
        addActionListener {
            if (currentScanJob?.isActive == true) {
                currentScanJob?.cancel()
                summaryLabel.text = "Canceling scan..."
            } else {
                runProjectScan()
            }
        }
    }

    private val filterButton = BridgeUiUtils.createStyledButton("Filter", Color(0x63, 0x66, 0xF1)).apply {
        addActionListener {
            val allItems = allResultsByFile.values.flatMap { it.items }
            DiagnosticsFilterPopup.show(project, this, allItems) {
                applyCurrentFilter()
            }
        }
    }

    private val progressBar = JProgressBar(0, 100).apply {
        isVisible = false
        isStringPainted = true
        preferredSize = Dimension(110, 18)
        font = Font("Segoe UI", Font.BOLD, 10)
        foreground = BridgeColors.accentBlue
    }

    private val treeModel = DiagnosticsTreeModel()

    private val diagnosticsTreeTable = TreeTable(treeModel).apply {
        setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        rowSelectionAllowed = true
        columnSelectionAllowed = false
        cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
        tree.isRootVisible = false
        tree.showsRootHandles = true
    }

    init {
        background = BridgeColors.bgMain
        BridgeUiUtils.styleTable(diagnosticsTreeTable)

        // Custom column widths
        diagnosticsTreeTable.columnModel.getColumn(0).preferredWidth = 240 // File / Location
        diagnosticsTreeTable.columnModel.getColumn(1).preferredWidth = 50  // Line
        diagnosticsTreeTable.columnModel.getColumn(2).preferredWidth = 85  // Severity
        diagnosticsTreeTable.columnModel.getColumn(3).preferredWidth = 350 // Message / Total Summary
        diagnosticsTreeTable.columnModel.getColumn(4).preferredWidth = 160 // AI Action
        diagnosticsTreeTable.columnModel.getColumn(4).cellRenderer = DiagnosticsAiActionRenderer()

        // Custom cell renderer for Severity column
        val severityRenderer = object : DefaultTableCellRenderer() {
            override fun getTableCellRendererComponent(
                table: JTable?,
                value: Any?,
                isSelected: Boolean,
                hasFocus: Boolean,
                row: Int,
                column: Int
            ): Component {
                val c = super.getTableCellRendererComponent(table, value, isSelected, hasFocus, row, column)
                if (!isSelected) {
                    val severityStr = value?.toString() ?: ""
                    c.foreground = when (severityStr.uppercase()) {
                        "ERROR" -> Color(0xEF, 0x44, 0x44)
                        "WARNING" -> Color(0xF5, 0x9E, 0x0B)
                        "WEAK_WARNING" -> Color(0x60, 0xA5, 0xFA)
                        "INFO", "INFORMATION" -> Color(0x38, 0xBD, 0xF8)
                        else -> BridgeColors.textMuted
                    }
                    font = font.deriveFont(Font.BOLD)
                }
                return c
            }
        }
        diagnosticsTreeTable.columnModel.getColumn(2).cellRenderer = severityRenderer

        // Row Click: Clicking a file row expands/collapses it downwards; clicking an issue navigates to code
        diagnosticsTreeTable.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                val row = diagnosticsTreeTable.rowAtPoint(e.point)
                if (row < 0) return
                val col = diagnosticsTreeTable.columnAtPoint(e.point)

                // Column 4 is "AI Action": dispatch directly to Copy or Fix
                if (col == 4) {
                    DiagnosticsAiActionRenderer.handleCellClick(project, diagnosticsTreeTable, e) { msg ->
                        showNotificationBalloon(msg)
                    }
                    return
                }

                val path = diagnosticsTreeTable.tree.getPathForRow(row) ?: return
                when (val node = path.lastPathComponent) {
                    is FileNode -> {
                        if (col > 0) {
                            if (diagnosticsTreeTable.tree.isExpanded(path)) {
                                diagnosticsTreeTable.tree.collapsePath(path)
                            } else {
                                diagnosticsTreeTable.tree.expandPath(path)
                            }
                        } else {
                            val bounds = diagnosticsTreeTable.tree.getPathBounds(path)
                            if (bounds != null && e.x >= bounds.x) {
                                if (diagnosticsTreeTable.tree.isExpanded(path)) {
                                    diagnosticsTreeTable.tree.collapsePath(path)
                                } else {
                                    diagnosticsTreeTable.tree.expandPath(path)
                                }
                            }
                        }
                    }
                    is IssueNode -> {
                        openFileAtLine(node.relativePath, node.line)
                    }
                }
            }
        })

        // Header controls bar (clean and minimal)
        val headerPanel = JPanel(BorderLayout()).apply {
            background = BridgeColors.bgHeader
            border = BorderFactory.createCompoundBorder(
                BorderFactory.createMatteBorder(0, 0, 1, 0, Color(0x3C, 0x3F, 0x41)),
                BorderFactory.createEmptyBorder(6, 8, 6, 8)
            )

            val leftPanel = JPanel(FlowLayout(FlowLayout.LEFT, 8, 0)).apply {
                isOpaque = false
                add(refreshButton)
                add(scanProjectButton)
                add(filterButton)
                add(includeWarningsCheck)
                add(progressBar)
            }

            add(leftPanel, BorderLayout.WEST)
            add(summaryLabel, BorderLayout.EAST)
        }

        val scrollPane = JBScrollPane(diagnosticsTreeTable).apply {
            border = BorderFactory.createEmptyBorder()
            viewport.background = BridgeColors.bgDark
        }

        add(headerPanel, BorderLayout.NORTH)
        add(scrollPane, BorderLayout.CENTER)

        // Load persisted state immediately on initialization
        loadPersistedState()
    }

    /**
     * Applies inspection filtering on raw scan records and refreshes the TreeTable.
     */
    fun applyCurrentFilter() {
        val disabledIds = DiagnosticsFilterPopup.getDisabledInspectionIds(project)
        treeModel.clear()

        var totalVisibleErrors = 0
        var totalVisibleWarnings = 0

        for (record in allResultsByFile.values) {
            val visibleItems = record.items.filter { item ->
                val id = item.inspectionId.trim().ifBlank { "Other" }
                id !in disabledIds
            }

            if (visibleItems.isNotEmpty()) {
                val errs = visibleItems.count { it.severity == "ERROR" }
                val warns = visibleItems.count { it.severity != "ERROR" }
                totalVisibleErrors += errs
                totalVisibleWarnings += warns

                treeModel.addOrUpdateFile(
                    fileName = record.fileName,
                    relativePath = record.relativePath,
                    errorsCount = errs,
                    warningsCount = warns,
                    diagnostics = visibleItems
                )
            }
        }

        val rootPath = TreePath(treeModel.rootNode)
        diagnosticsTreeTable.tree.expandPath(rootPath)

        val filterSuffix = if (disabledIds.isNotEmpty()) " (${disabledIds.size} rule(s) hidden)" else ""
        filterButton.text = if (disabledIds.isNotEmpty()) "Filter (${disabledIds.size} hidden)" else "Filter"

        if (allResultsByFile.isNotEmpty()) {
            summaryLabel.text = "Scanned ${allResultsByFile.size} files: $totalVisibleErrors Error(s), $totalVisibleWarnings Warning(s)$filterSuffix"
            summaryLabel.foreground = if (totalVisibleErrors > 0) Color(0xEF, 0x44, 0x44) else if (totalVisibleWarnings > 0) Color(0xF5, 0x9E, 0x0B) else BridgeColors.statusGreen
        }
    }

    /**
     * Loads saved diagnostics state from persistent storage.
     */
    private fun loadPersistedState() {
        try {
            val stateService = DiagnosticsState.getInstance(project)
            val state = stateService.state
            if (state.items.isNotEmpty()) {
                allResultsByFile.clear()
                val grouped = state.items.groupBy { it.relativePath }
                for ((relPath, items) in grouped) {
                    val first = items.first()
                    val diags = items.map {
                        IdeDiagnosticsService.DiagnosticItem(
                            line = it.line,
                            column = it.column,
                            severity = it.severity,
                            message = it.message,
                            inspectionId = it.inspectionId
                        )
                    }
                    allResultsByFile[relPath] = FileScanRecord(first.file, relPath, diags)
                }
                applyCurrentFilter()
            }
        } catch (_: Exception) {}
    }

    /**
     * Saves all raw diagnostics to persistent state storage.
     */
    private fun saveCurrentState(summary: String, totalErrors: Int, totalWarnings: Int) {
        try {
            val stateService = DiagnosticsState.getInstance(project)
            val state = stateService.state
            state.summaryText = summary
            state.totalErrors = totalErrors
            state.totalWarnings = totalWarnings
            state.lastScanTimestamp = System.currentTimeMillis()
            state.items.clear()
            for (record in allResultsByFile.values) {
                for (item in record.items) {
                    state.items.add(
                        DiagnosticsState.StoredDiagnosticItem(
                            file = record.fileName,
                            relativePath = record.relativePath,
                            line = item.line,
                            column = item.column,
                            severity = item.severity,
                            message = item.message,
                            inspectionId = item.inspectionId
                        )
                    )
                }
            }
        } catch (_: Exception) {}
    }

    /**
     * Executes headless whole-project scanning with real-time TreeTable streaming.
     */
    fun runProjectScan() {
        summaryLabel.text = "Scanning project files sequentially..."
        summaryLabel.foreground = BridgeColors.textMuted
        refreshButton.isEnabled = false
        scanProjectButton.text = "Stop Scan"
        scanProjectButton.background = Color(0xEF, 0x44, 0x44)
        scanProjectButton.isEnabled = true
        progressBar.isVisible = true
        progressBar.value = 0
        progressBar.string = "Starting..."

        allResultsByFile.clear()
        treeModel.clear()

        currentScanJob = scope.launch {
            val includeWarnings = includeWarningsCheck.isSelected
            val disabledIds = DiagnosticsFilterPopup.getDisabledInspectionIds(project)
            var totalRunningErrors = 0
            var totalRunningWarnings = 0

            try {
                val report = ProjectDiagnosticsScanner.scanProject(
                    project = project,
                    includeWarnings = includeWarnings,
                    maxFiles = Int.MAX_VALUE,
                    batchSize = 50,
                    onBatchScanned = { batch, current, total ->
                        ApplicationManager.getApplication().invokeLater {
                            progressBar.maximum = total
                            progressBar.value = current
                            progressBar.string = "$current / $total"

                            val disabledIds = DiagnosticsFilterPopup.getDisabledInspectionIds(project)

                            for (fileResult in batch) {
                                totalRunningErrors += fileResult.errorsCount
                                totalRunningWarnings += fileResult.warningsCount

                                allResultsByFile[fileResult.relativePath] = FileScanRecord(
                                    fileName = fileResult.file,
                                    relativePath = fileResult.relativePath,
                                    items = fileResult.diagnostics
                                )

                                val visibleItems = fileResult.diagnostics.filter {
                                    val id = it.inspectionId.trim().ifBlank { "Other" }
                                    id !in disabledIds
                                }

                                if (visibleItems.isNotEmpty()) {
                                    val errs = visibleItems.count { it.severity == "ERROR" }
                                    val warns = visibleItems.count { it.severity != "ERROR" }
                                    treeModel.addOrUpdateFile(
                                        fileName = fileResult.file,
                                        relativePath = fileResult.relativePath,
                                        errorsCount = errs,
                                        warningsCount = warns,
                                        diagnostics = visibleItems
                                    )
                                }
                            }

                            val rootPath = TreePath(treeModel.rootNode)
                            if (!diagnosticsTreeTable.tree.isExpanded(rootPath)) {
                                diagnosticsTreeTable.tree.expandPath(rootPath)
                            }

                            val lastFile = batch.lastOrNull()?.file ?: ""
                            summaryLabel.text = "Scanning ($current/$total): $lastFile | Issues: $totalRunningErrors Err, $totalRunningWarnings Warn"
                            summaryLabel.foreground = if (totalRunningErrors > 0) Color(0xEF, 0x44, 0x44) else if (totalRunningWarnings > 0) Color(0xF5, 0x9E, 0x0B) else BridgeColors.textMuted
                        }
                    }
                )

                ApplicationManager.getApplication().invokeLater {
                    applyCurrentFilter()

                    if (!report.success) {
                        summaryLabel.text = report.error ?: "Project scan failed"
                        summaryLabel.foreground = Color(0xEF, 0x44, 0x44)
                        return@invokeLater
                    }

                    saveCurrentState(summaryLabel.text, report.totalErrors, report.totalWarnings)
                }
            } catch (e: Exception) {
                ApplicationManager.getApplication().invokeLater {
                    summaryLabel.text = "Scan error: ${e.message}"
                    summaryLabel.foreground = Color(0xEF, 0x44, 0x44)
                }
            } finally {
                ApplicationManager.getApplication().invokeLater {
                    refreshButton.isEnabled = true
                    scanProjectButton.text = "Scan Project"
                    scanProjectButton.background = BridgeColors.btnGreen
                    scanProjectButton.isEnabled = true
                    progressBar.isVisible = false
                }
            }
        }
    }

    /**
     * Reactively queries IdeDiagnosticsService for active file only when user clicks Refresh File.
     */
    private fun showNotificationBalloon(message: String) {
        try {
            val balloon = com.intellij.openapi.ui.popup.JBPopupFactory.getInstance()
                .createHtmlTextBalloonBuilder(message, com.intellij.openapi.ui.MessageType.INFO, null)
                .setFadeoutTime(3500)
                .createBalloon()
            balloon.show(com.intellij.ui.awt.RelativePoint.getCenterOf(diagnosticsTreeTable), com.intellij.openapi.ui.popup.Balloon.Position.above)
        } catch (_: Exception) {
            summaryLabel.text = message
        }
    }

    fun refreshDiagnostics(targetFile: String? = null) {
        summaryLabel.text = "Analyzing active file diagnostics..."
        summaryLabel.foreground = BridgeColors.textMuted
        refreshButton.isEnabled = false

        scope.launch {
            try {
                val includeWarnings = includeWarningsCheck.isSelected
                val result = IdeDiagnosticsService.collectDiagnostics(
                    project = project,
                    targetFilePath = targetFile,
                    includeWarnings = includeWarnings
                )

                SwingUtilities.invokeLater {
                    if (!result.success) {
                        val isNoFile = result.error?.contains("No file", ignoreCase = true) == true
                        summaryLabel.text = if (isNoFile) "? Open a file in the editor to inspect diagnostics" else (result.error ?: "Failed to collect diagnostics.")
                        summaryLabel.foreground = if (isNoFile) BridgeColors.textMuted else Color(0xEF, 0x44, 0x44)
                        return@invokeLater
                    }

                    allResultsByFile[result.file] = FileScanRecord(
                        fileName = result.file,
                        relativePath = result.file,
                        items = result.items
                    )

                    applyCurrentFilter()

                    val totalErrs = allResultsByFile.values.sumOf { it.items.count { i -> i.severity == "ERROR" } }
                    val totalWarns = allResultsByFile.values.sumOf { it.items.count { i -> i.severity != "ERROR" } }
                    saveCurrentState(summaryLabel.text, totalErrs, totalWarns)
                }
            } catch (e: Exception) {
                SwingUtilities.invokeLater {
                    summaryLabel.text = "Error: ${e.message}"
                    summaryLabel.foreground = Color(0xEF, 0x44, 0x44)
                }
            } finally {
                SwingUtilities.invokeLater {
                    refreshButton.isEnabled = true
                }
            }
        }
    }
}