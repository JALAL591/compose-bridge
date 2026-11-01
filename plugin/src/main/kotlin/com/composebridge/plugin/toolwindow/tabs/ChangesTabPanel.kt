package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.diff.DiffContentFactory
import com.intellij.diff.DiffManager
import com.intellij.diff.requests.SimpleDiffRequest
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.table.JBTable
import java.awt.*
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent
import java.io.File
import javax.swing.*
import javax.swing.table.DefaultTableModel

class ChangesTabPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner,
    private val openFileAtLine: (String, Int) -> Unit,
    private val onPatternsRefreshNeeded: () -> Unit,
    val changesBadgeLabel: JLabel
) : JPanel(BorderLayout()) {

    private val gson = Gson()

    @Volatile
    private var lastModifiedFilesJson: String = ""
    @Volatile
    private var isRefreshingChanges: Boolean = false

    val changesSummaryLabel = JLabel(" ").apply {
        foreground = BridgeColors.statusGreen
        font = Font("Segoe UI", Font.BOLD, 13)
        border = BorderFactory.createEmptyBorder(10, 16, 8, 16)
    }

    val changesTableModel = object : DefaultTableModel(
        arrayOf("File", "Changes", "Patterns"), 0
    ) {
        override fun isCellEditable(row: Int, column: Int): Boolean = false
    }
    val changesTable = JBTable(changesTableModel)

    val changesListContainer = JPanel().apply {
        layout = BoxLayout(this, BoxLayout.Y_AXIS)
        background = BridgeColors.bgMain
    }

    val changesFilesList = mutableListOf<String>()
    val changesLinesList = mutableListOf<Int>()

    val sharedTokensPanel = SharedTokensPanel(project, pythonRunner)

    init {
        background = BridgeColors.bgMain
        BridgeUiUtils.styleTable(changesTable)
        changesTable.setSelectionMode(ListSelectionModel.SINGLE_SELECTION)
        changesTable.rowSelectionAllowed = true
        changesTable.columnSelectionAllowed = false
        changesTable.cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)

        add(changesSummaryLabel, BorderLayout.NORTH)

        val pendingFilesPanel = JPanel(BorderLayout()).apply { background = BridgeColors.bgMain }
        val changesScrollPane = JBScrollPane(changesListContainer).apply {
            border = BorderFactory.createEmptyBorder()
            verticalScrollBar.unitIncrement = 16
        }
        pendingFilesPanel.add(changesScrollPane, BorderLayout.CENTER)
        val hintLabel = JLabel("Click any file to expand/collapse. Each change has independent Approve and Reject controls.").apply {
            foreground = BridgeColors.textMuted
            font = Font("Segoe UI", Font.ITALIC, 11)
            border = BorderFactory.createEmptyBorder(4, 16, 4, 16)
        }
        pendingFilesPanel.add(hintLabel, BorderLayout.SOUTH)

        val changesSplitPane = JSplitPane(JSplitPane.VERTICAL_SPLIT, pendingFilesPanel, sharedTokensPanel).apply {
            isContinuousLayout = true
            dividerSize = 6
            resizeWeight = 0.75
            border = BorderFactory.createEmptyBorder()
            background = BridgeColors.bgMain
        }
        add(changesSplitPane, BorderLayout.CENTER)

        val changesBottom = JPanel(FlowLayout(FlowLayout.LEFT, 12, 10)).apply {
            background = BridgeColors.bgTabBar
            border = BorderFactory.createEmptyBorder(4, 8, 4, 8)
        }
        val viewDiffBtn = BridgeUiUtils.createStyledButton("View Diff", BridgeColors.accentBlue, Color.WHITE)
        viewDiffBtn.toolTipText = "Inspect before vs current diff for selected file"
        viewDiffBtn.addActionListener { onViewDiffSelectedFile() }

        val approveBtn = BridgeUiUtils.createStyledButton("Approve", BridgeColors.btnGreen, Color.WHITE)
        approveBtn.toolTipText = "Approve changes for selected file"
        approveBtn.addActionListener { onApproveSelectedFile() }

        val rejectBtn = BridgeUiUtils.createStyledButton("Reject", BridgeColors.btnRed, Color.WHITE)
        rejectBtn.toolTipText = "Revert changes for selected file"
        rejectBtn.addActionListener { onRejectSelectedFile() }

        val approveAllBtn = BridgeUiUtils.createStyledButton("Approve All", Color(0x15, 0x80, 0x3D), Color.WHITE)
        approveAllBtn.addActionListener { onApproveAllFiles() }

        val rejectAllBtn = BridgeUiUtils.createStyledButton("Reject All", Color(0xB9, 0x1C, 0x1C), Color.WHITE)
        rejectAllBtn.addActionListener { onRejectAllFiles() }

        val refreshBtn = BridgeUiUtils.createStyledButton("Refresh", BridgeColors.btnGray, Color.WHITE)
        refreshBtn.addActionListener { refreshChanges() }

        changesBottom.add(viewDiffBtn)
        changesBottom.add(approveBtn)
        changesBottom.add(rejectBtn)
        changesBottom.add(approveAllBtn)
        changesBottom.add(rejectAllBtn)
        changesBottom.add(refreshBtn)
        add(changesBottom, BorderLayout.SOUTH)

        // Single or Double-click row in Changes -> open file directly in Editor at modified line
        changesTable.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                val row = changesTable.rowAtPoint(e.point)
                if (row >= 0 && row < changesFilesList.size) {
                    changesTable.setRowSelectionInterval(row, row)
                    val file = changesFilesList[row]
                    val line = if (row < changesLinesList.size) changesLinesList[row] else 1
                    openFileAtLine(file, line)
                }
            }
        })
    }

    fun refreshChanges() {
        if (isRefreshingChanges) return
        isRefreshingChanges = true

        Thread {
            try {
                val json = pythonRunner.listModifiedFiles()
                SwingUtilities.invokeLater {
                    try {
                        parseAndFillChanges(json)
                    } finally {
                        isRefreshingChanges = false
                    }
                }
            } catch (e: Exception) {
                isRefreshingChanges = false
            }
        }.start()

        sharedTokensPanel.refreshSharedTokens()
    }

    private fun parseAndFillChanges(json: String) {
        try {
            val cleanJson = BridgeUiUtils.extractJson(json)
            if (cleanJson == lastModifiedFilesJson && cleanJson.isNotBlank()) {
                return // Content unchanged: skip rebuilding UI to prevent flickering!
            }
            lastModifiedFilesJson = cleanJson

            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val success = root.get("success")?.asBoolean ?: (root.get("type")?.asString == "user_sync_ack" && root.get("status")?.asString != "error")
            if (!success) {
                changesSummaryLabel.text = "Error: ${root.get("error")?.asString}"
                changesBadgeLabel.isVisible = false
                changesListContainer.removeAll()
                changesListContainer.revalidate()
                changesListContainer.repaint()
                return
            }
            val count = root.get("count")?.asInt ?: 0
            changesListContainer.removeAll()
            changesTableModel.rowCount = 0
            changesFilesList.clear()
            changesLinesList.clear()

            if (count == 0) {
                changesSummaryLabel.text = "No pending file changes on disk"
                changesBadgeLabel.isVisible = false
                val emptyPanel = JPanel(FlowLayout(FlowLayout.CENTER, 10, 30)).apply {
                    isOpaque = false
                    val lbl = JLabel("All files clean. No pending changes on disk.").apply {
                        font = Font("Segoe UI", Font.PLAIN, 13)
                        foreground = BridgeColors.textMuted
                    }
                    add(lbl)
                }
                changesListContainer.add(emptyPanel)
                changesListContainer.revalidate()
                changesListContainer.repaint()
                return
            }
            changesSummaryLabel.text = "$count file(s) modified on disk - Manage granular diffs below"
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
                    val firstLine = if (obj.has("first_line") && !obj.get("first_line").isJsonNull) obj.get("first_line").asInt else 1
                    changesFilesList.add(file)
                    changesLinesList.add(if (firstLine > 0) firstLine else 1)
                    val changesStr = if (changeCount == 1) "1 change" else "$changeCount changes"
                    changesTableModel.addRow(arrayOf(file, changesStr, patterns))

                    // Build expandable File Card
                    val fileCard = buildFileCard(file, changeCount, firstLine, obj)
                    changesListContainer.add(fileCard)
                    changesListContainer.add(Box.createVerticalStrut(8))
                }
                changesListContainer.add(Box.createVerticalGlue())
            }
            changesListContainer.revalidate()
            changesListContainer.repaint()
        } catch (e: Exception) {
            changesSummaryLabel.text = "Error: ${e.message}"
            changesBadgeLabel.isVisible = false
        }
    }

    private fun buildFileCard(file: String, changeCount: Int, firstLine: Int, obj: JsonObject): JPanel {
        val fileCard = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            background = BridgeColors.bgDark
            border = BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(BridgeColors.bgHeader, 1, true),
                BorderFactory.createEmptyBorder(2, 2, 2, 2)
            )
            alignmentX = Component.LEFT_ALIGNMENT
        }

        val fileHeader = JPanel(BorderLayout(8, 0)).apply {
            background = Color(0x28, 0x2C, 0x34)
            border = BorderFactory.createEmptyBorder(8, 12, 8, 12)
            cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
            alignmentX = Component.LEFT_ALIGNMENT
            maximumSize = Dimension(Integer.MAX_VALUE, 44)
        }

        val westPanel = JPanel(FlowLayout(FlowLayout.LEFT, 8, 0)).apply { isOpaque = false }
        val toggleIcon = JLabel("[v]").apply {
            font = Font("Segoe UI", Font.BOLD, 12)
            foreground = BridgeColors.textMuted
        }
        val fileNameOnly = File(file).name
        val fileNameLabel = JLabel(fileNameOnly).apply {
            font = Font("Segoe UI", Font.BOLD, 13)
            foreground = Color.WHITE
            toolTipText = file
        }
        val filePathSub = JLabel("(${file})").apply {
            font = Font("Segoe UI", Font.PLAIN, 11)
            foreground = BridgeColors.textMuted
        }
        val badge = JLabel("$changeCount change${if (changeCount == 1) "" else "s"}").apply {
            isOpaque = true
            background = BridgeColors.accentBlue
            foreground = Color.WHITE
            font = Font("Segoe UI", Font.BOLD, 10)
            border = BorderFactory.createEmptyBorder(2, 6, 2, 6)
        }
        westPanel.add(toggleIcon)
        westPanel.add(fileNameLabel)
        westPanel.add(filePathSub)
        westPanel.add(badge)
        fileHeader.add(westPanel, BorderLayout.WEST)

        val eastPanel = JPanel(FlowLayout(FlowLayout.RIGHT, 6, 0)).apply { isOpaque = false }
        val diffBtn = BridgeUiUtils.createStyledButton("Diff", BridgeColors.accentBlue, Color.WHITE).apply {
            font = Font("Segoe UI", Font.PLAIN, 11)
            preferredSize = Dimension(60, 24)
            addActionListener { onViewDiffFile(file) }
        }
        val approveFileBtn = BridgeUiUtils.createStyledButton("Approve File", BridgeColors.btnGreen, Color.WHITE).apply {
            font = Font("Segoe UI", Font.BOLD, 11)
            preferredSize = Dimension(105, 24)
            addActionListener { onApproveFile(file) }
        }
        val rejectFileBtn = BridgeUiUtils.createStyledButton("Reject File", BridgeColors.btnRed, Color.WHITE).apply {
            font = Font("Segoe UI", Font.BOLD, 11)
            preferredSize = Dimension(95, 24)
            addActionListener { onRejectFile(file) }
        }
        eastPanel.add(diffBtn)
        eastPanel.add(approveFileBtn)
        eastPanel.add(rejectFileBtn)
        fileHeader.add(eastPanel, BorderLayout.EAST)

        val hunksPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            background = BridgeColors.bgMain
            border = BorderFactory.createEmptyBorder(6, 16, 8, 12)
            alignmentX = Component.LEFT_ALIGNMENT
            maximumSize = Dimension(Integer.MAX_VALUE, Integer.MAX_VALUE)
            isVisible = true
        }

        var isExpanded = true
        val toggle = {
            isExpanded = !isExpanded
            toggleIcon.text = if (isExpanded) "[v]" else "[>]"
            hunksPanel.isVisible = isExpanded
            fileCard.revalidate()
            fileCard.repaint()
        }
        fileHeader.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                if (e.clickCount == 2) {
                    openFileAtLine(file, firstLine)
                } else {
                    toggle()
                }
            }
        })
        toggleIcon.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) { toggle() }
        })

        val changesArr = if (obj.has("changes") && obj.get("changes").isJsonArray) obj.getAsJsonArray("changes") else null
        if (changesArr != null && changesArr.size() > 0) {
            for (chElem in changesArr) {
                val chObj = chElem.asJsonObject
                val hunkId = if (chObj.has("id")) chObj.get("id").asString else "h1"
                val lineStart = if (chObj.has("line_start")) chObj.get("line_start").asInt else firstLine
                val lineEnd = if (chObj.has("line_end")) chObj.get("line_end").asInt else lineStart
                val oldText = if (chObj.has("old")) chObj.get("old").asString else ""
                val newText = if (chObj.has("new")) chObj.get("new").asString else ""

                val hunkRow = buildHunkRow(file, hunkId, lineStart, lineEnd, oldText, newText)
                hunksPanel.add(hunkRow)
                hunksPanel.add(Box.createVerticalStrut(4))
            }
        } else {
            val noHunkLbl = JLabel("File modified on disk (no discrete hunks available)").apply {
                font = Font("Segoe UI", Font.ITALIC, 11)
                foreground = BridgeColors.textMuted
                border = BorderFactory.createEmptyBorder(4, 6, 4, 6)
            }
            hunksPanel.add(noHunkLbl)
        }

        fileCard.add(fileHeader)
        fileCard.add(hunksPanel)
        return fileCard
    }

    private fun buildHunkRow(file: String, hunkId: String, lineStart: Int, lineEnd: Int, oldText: String, newText: String): JPanel {
        val hunkRow = JPanel(BorderLayout(8, 0)).apply {
            background = Color(0x21, 0x25, 0x2B)
            border = BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(Color(0x35, 0x3B, 0x45), 1, true),
                BorderFactory.createEmptyBorder(4, 8, 4, 8)
            )
            alignmentX = Component.LEFT_ALIGNMENT
            maximumSize = Dimension(Integer.MAX_VALUE, 90)
        }

        val infoPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            isOpaque = false
            preferredSize = Dimension(120, 40)
        }
        val lineStr = if (lineEnd > lineStart) "Lines $lineStart-$lineEnd" else "Line $lineStart"
        val lineLbl = JLabel(lineStr).apply {
            font = Font("Segoe UI", Font.BOLD, 12)
            foreground = BridgeColors.accentBlue
            cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
            toolTipText = "Click to jump to line in editor"
            addMouseListener(object : MouseAdapter() {
                override fun mouseClicked(e: MouseEvent) {
                    openFileAtLine(file, lineStart)
                }
            })
        }
        val isAutoImport = newText.trim().startsWith("import com.composebridge.") ||
                           (newText.trim().startsWith("import ") && newText.contains("AppColors"))
        val idLblText = if (isAutoImport) "$hunkId [Auto-Import]" else hunkId
        val idLbl = JLabel(idLblText).apply {
            font = Font("Segoe UI", Font.PLAIN, 10)
            foreground = if (isAutoImport) BridgeColors.accentPurple else BridgeColors.textMuted
            toolTipText = if (isAutoImport) "Auto-managed: approved/rejected atomically with code usage" else null
        }
        infoPanel.add(lineLbl)
        infoPanel.add(idLbl)
        hunkRow.add(infoPanel, BorderLayout.WEST)

        val diffPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            isOpaque = false
            border = BorderFactory.createEmptyBorder(2, 4, 2, 4)
        }
        if (oldText.isNotEmpty()) {
            val oldView = createDiffSnippet("-", oldText, Color(0xF8, 0x71, 0x71), Color(0x3B, 0x18, 0x18))
            diffPanel.add(oldView)
        }
        if (newText.isNotEmpty()) {
            val newView = createDiffSnippet("+", newText, BridgeColors.statusGreen, Color(0x14, 0x33, 0x1E))
            diffPanel.add(newView)
        }
        hunkRow.add(diffPanel, BorderLayout.CENTER)

        val actionsPanel = JPanel(FlowLayout(FlowLayout.RIGHT, 6, 4)).apply {
            isOpaque = false
        }
        val approveHunkBtn = BridgeUiUtils.createStyledButton("Approve Change", BridgeColors.btnGreen, Color.WHITE).apply {
            font = Font("Segoe UI", Font.BOLD, 11)
            preferredSize = Dimension(135, 24)
            toolTipText = "Accept this specific change only"
            addActionListener { onApproveChange(file, hunkId) }
        }
        val rejectHunkBtn = BridgeUiUtils.createStyledButton("Reject Change", BridgeColors.btnRed, Color.WHITE).apply {
            font = Font("Segoe UI", Font.BOLD, 11)
            preferredSize = Dimension(125, 24)
            toolTipText = "Revert this specific change only"
            addActionListener { onRejectChange(file, hunkId) }
        }
        actionsPanel.add(approveHunkBtn)
        actionsPanel.add(rejectHunkBtn)
        hunkRow.add(actionsPanel, BorderLayout.EAST)

        return hunkRow
    }

    private fun createDiffSnippet(prefix: String, text: String, fg: Color, bg: Color): JComponent {
        val clean = text.trimEnd('\r', '\n')
        val lines = clean.lines()
        if (lines.size <= 1) {
            return JLabel("$prefix $clean").apply {
                font = Font(Font.MONOSPACED, Font.PLAIN, 12)
                foreground = fg
                isOpaque = true
                background = bg
                border = BorderFactory.createEmptyBorder(2, 6, 2, 6)
                alignmentX = Component.LEFT_ALIGNMENT
            }
        }
        val panel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            isOpaque = true
            background = bg
            border = BorderFactory.createEmptyBorder(2, 6, 2, 6)
            alignmentX = Component.LEFT_ALIGNMENT
        }
        for (line in lines.take(5)) {
            panel.add(JLabel("$prefix $line").apply {
                font = Font(Font.MONOSPACED, Font.PLAIN, 12)
                foreground = fg
            })
        }
        if (lines.size > 5) {
            panel.add(JLabel("... (${lines.size - 5} more lines)").apply {
                font = Font("Segoe UI", Font.ITALIC, 10)
                foreground = fg
            })
        }
        return panel
    }

    private fun onApproveChange(file: String, hunkId: String) {
        lastModifiedFilesJson = ""
        Thread {
            val json = pythonRunner.approveChange(file, hunkId)
            SwingUtilities.invokeLater {
                try {
                    val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
                    if (root.get("success")?.asBoolean == true) {
                        BridgeUiUtils.refreshVfsAndDocument(project, file)
                    } else {
                        val err = root.get("error")?.asString ?: "Failed to approve change"
                        Messages.showErrorDialog(err, "ComposeBridge Error")
                    }
                } catch (_: Exception) {}
                refreshChanges()
            }
        }.start()
    }

    private fun onRejectChange(file: String, hunkId: String) {
        lastModifiedFilesJson = ""
        Thread {
            val json = pythonRunner.rejectChange(file, hunkId)
            SwingUtilities.invokeLater {
                try {
                    val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
                    if (root.get("success")?.asBoolean == true) {
                        BridgeUiUtils.refreshVfsAndDocument(project, file)
                    } else {
                        val err = root.get("error")?.asString ?: "Failed to reject change"
                        Messages.showErrorDialog(err, "ComposeBridge Error")
                    }
                } catch (_: Exception) {}
                refreshChanges()
            }
        }.start()
    }

    private fun onApproveFile(file: String) {
        val fileName = File(file).name
        val choice = Messages.showYesNoDialog(
            "Approve changes for '$fileName'?\n\nThis will mark modifications in this file as accepted and remove it from the pending journal.",
            "ComposeBridge - Approve File",
            Messages.getQuestionIcon()
        )
        if (choice != Messages.YES) return

        Thread {
            val json = pythonRunner.approveFileChanges(file)
            SwingUtilities.invokeLater {
                try {
                    val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
                    if (root.get("success")?.asBoolean == true) {
                        BridgeUiUtils.refreshVfsAndDocument(project, file)
                        Messages.showInfoMessage("Changes approved for '$fileName'.", "ComposeBridge")
                    } else {
                        val err = root.get("error")?.asString ?: "Failed to approve changes"
                        Messages.showErrorDialog(err, "ComposeBridge Error")
                    }
                } catch (_: Exception) {}
                refreshChanges()
            }
        }.start()
    }

    private fun onRejectFile(file: String) {
        val fileName = File(file).name
        Thread {
            val json = pythonRunner.rejectFileChanges(file, force = false)
            SwingUtilities.invokeLater {
                try {
                    val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
                    val errorCode = root.get("error_code")?.asString

                    if (errorCode == "EXTERNAL_MODIFICATION_DETECTED") {
                        val warningMsg = root.get("message")?.asString
                            ?: "This file has external modifications in the IDE. Reverting will overwrite your latest edits!\n\nDo you want to FORCE revert?"
                        val choice = Messages.showYesNoDialog(
                            warningMsg,
                            "ComposeBridge — Warning: Conflict Detected",
                            Messages.getWarningIcon()
                        )
                        if (choice == Messages.YES) {
                            Thread {
                                pythonRunner.rejectFileChanges(file, force = true)
                                SwingUtilities.invokeLater {
                                    BridgeUiUtils.refreshVfsAndDocument(project, file)
                                    refreshChanges()
                                }
                            }.start()
                        }
                    } else if (root.get("success")?.asBoolean == true) {
                        BridgeUiUtils.refreshVfsAndDocument(project, file)
                        Messages.showInfoMessage("Reverted changes for '$fileName'.", "ComposeBridge")
                    } else {
                        val err = root.get("error")?.asString ?: "Failed to reject changes"
                        Messages.showErrorDialog(err, "ComposeBridge Error")
                    }
                } catch (_: Exception) {}
                refreshChanges()
            }
        }.start()
    }

    fun onViewDiffFile(file: String) {
        Thread {
            val json = pythonRunner.getFileDiff(file)
            SwingUtilities.invokeLater {
                try {
                    val cleanJson = BridgeUiUtils.extractJson(json)
                    val root = gson.fromJson(cleanJson, JsonObject::class.java)
                    if (root.get("success")?.asBoolean == true) {
                        val originalText = root.get("original_content")?.asString ?: ""
                        val currentText = root.get("current_content")?.asString ?: ""
                        val fileName = File(file).name

                        val contentFactory = DiffContentFactory.getInstance()
                        val originalContent = contentFactory.create(originalText)
                        val currentContent = contentFactory.create(currentText)

                        val request = SimpleDiffRequest(
                            "Diff: $fileName (Before vs Current)",
                            originalContent,
                            currentContent,
                            "Original (Baseline)",
                            "Current on Disk (Modified)"
                        )
                        DiffManager.getInstance().showDiff(project, request)
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

    private fun getSelectedOrFirstFile(): Pair<String, Int>? {
        if (changesFilesList.isEmpty()) return null
        var row = changesTable.selectedRow
        if (row < 0 || row >= changesFilesList.size) {
            row = 0
        }
        val file = changesFilesList[row]
        val line = if (row < changesLinesList.size) changesLinesList[row] else 1
        return Pair(file, line)
    }

    fun onViewDiffSelectedFile() {
        val target = getSelectedOrFirstFile()
        if (target == null) {
            Messages.showInfoMessage("No pending file changes on disk to view diff.", "ComposeBridge")
            return
        }
        onViewDiffFile(target.first)
    }

    fun onApproveSelectedFile() {
        val target = getSelectedOrFirstFile()
        if (target == null) {
            Messages.showInfoMessage("No pending file changes to approve.", "ComposeBridge")
            return
        }
        onApproveFile(target.first)
    }

    fun onRejectSelectedFile() {
        val target = getSelectedOrFirstFile()
        if (target == null) {
            Messages.showInfoMessage("No pending file changes to reject.", "ComposeBridge")
            return
        }
        onRejectFile(target.first)
    }

    fun onApproveAllFiles() {
        val choice = Messages.showYesNoDialog(
            "Approve all changes?\n\nThis will mark all changes as accepted and clear the journal.",
            "ComposeBridge — Approve All",
            Messages.getQuestionIcon()
        )
        if (choice != Messages.YES) return
        Thread {
            pythonRunner.approveAllFiles()
            SwingUtilities.invokeLater {
                BridgeUiUtils.refreshAllVfsAndDocuments()
                refreshChanges()
            }
        }.start()
    }

    fun onForceRejectAll() {
        val choice = Messages.showYesNoDialog(
            "Force revert all changes? This will clear the journal even if some file reverts fail!",
            "ComposeBridge — Force Reject All",
            Messages.getWarningIcon()
        )
        if (choice != Messages.YES) return
        Thread {
            pythonRunner.rejectAllFilesForce()
            SwingUtilities.invokeLater {
                BridgeUiUtils.refreshAllVfsAndDocuments()
                refreshChanges()
                onPatternsRefreshNeeded()
            }
        }.start()
    }

    fun onRejectAllFiles() {
        val choice = Messages.showYesNoDialog(
            "Revert all changes? This cannot be undone!",
            "ComposeBridge — Reject All",
            Messages.getWarningIcon()
        )
        if (choice != Messages.YES) return
        Thread {
            pythonRunner.rejectAllFiles()
            SwingUtilities.invokeLater {
                BridgeUiUtils.refreshAllVfsAndDocuments()
                refreshChanges()
                onPatternsRefreshNeeded()
            }
        }.start()
    }
}

