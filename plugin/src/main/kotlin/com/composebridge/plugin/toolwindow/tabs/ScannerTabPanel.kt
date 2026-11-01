package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.settings.ComposeBridgeConfigurable
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.openapi.options.ShowSettingsUtil
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

class ScannerTabPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner,
    private val openFileAtLine: (String, Int) -> Unit,
    private val onTokenSelectedCallback: (String) -> Unit,
    private val onScanFinishedCallbacks: (projectRoot: String) -> Unit
) : JPanel(BorderLayout()) {

    private val gson = Gson()

    val scanTableModel = object : DefaultTableModel(
        arrayOf("Name", "Value", "Location", "Type"), 0
    ) {
        override fun isCellEditable(row: Int, column: Int): Boolean = false
    }
    val scanTable = JBTable(scanTableModel)

    val scanSummaryLabel = JLabel("Press 'Scan Project' to analyze design tokens").apply {
        foreground = BridgeColors.statusGreen
        font = Font("Segoe UI", Font.BOLD, 13)
        border = BorderFactory.createEmptyBorder(10, 16, 8, 16)
    }

    val scanTopPanel = JPanel(BorderLayout())
    val brokenBannerPanel = JPanel(BorderLayout(10, 0)).apply {
        background = Color(0x3B, 0x11, 0x11)
        border = BorderFactory.createCompoundBorder(
            BorderFactory.createMatteBorder(0, 0, 1, 0, Color(0xEF, 0x44, 0x44)),
            BorderFactory.createEmptyBorder(6, 16, 6, 16)
        )
        isVisible = false
    }
    val brokenWarningLabel = JLabel("").apply {
        foreground = Color(0xFE, 0xCA, 0xCA)
        font = Font("Segoe UI", Font.BOLD, 12)
    }
    val viewBrokenButton = BridgeUiUtils.createStyledButton("⚠️ View Issues", Color(0xDC, 0x26, 0x26), Color.WHITE)
    private var currentBrokenFiles: com.google.gson.JsonArray? = null
    val activeBrokenFiles = mutableMapOf<String, JsonObject>()

    val siblingsPanel = JPanel(FlowLayout(FlowLayout.LEFT)).apply {
        background = BridgeColors.bgDark
        border = BorderFactory.createEmptyBorder(6, 12, 6, 12)
    }
    val siblingsTitleLabel = JLabel("Related tokens: ").apply {
        foreground = Color(0x93, 0xC5, 0xFD)
        font = Font("Segoe UI", Font.BOLD, 12)
    }

    init {
        background = BridgeColors.bgMain
        BridgeUiUtils.styleTable(scanTable)

        brokenBannerPanel.add(brokenWarningLabel, BorderLayout.CENTER)
        brokenBannerPanel.add(viewBrokenButton, BorderLayout.EAST)
        viewBrokenButton.addActionListener {
            showBrokenFilesDialog()
        }

        scanTopPanel.apply {
            background = BridgeColors.bgMain
            add(brokenBannerPanel, BorderLayout.NORTH)
            add(scanSummaryLabel, BorderLayout.CENTER)
        }
        add(scanTopPanel, BorderLayout.NORTH)
        add(JBScrollPane(scanTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
        add(siblingsPanel, BorderLayout.SOUTH)

        // Double-click row in Scan -> open file in Editor
        scanTable.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                if (e.clickCount == 2) {
                    val row = scanTable.rowAtPoint(e.point)
                    if (row >= 0 && row < scanTableModel.rowCount) {
                        val loc = scanTableModel.getValueAt(row, 2) as? String ?: ""
                        if (loc.isNotBlank()) {
                            val parts = loc.split(":")
                            val file = parts[0].trim()
                            val line = if (parts.size > 1) parts[1].trim().toIntOrNull() ?: 1 else 1
                            openFileAtLine(file, line)
                        }
                    }
                }
            }
        })

        // Select row in Scan -> Impact & Siblings
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
    }

    fun onScanProject() {
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
        scanSummaryLabel.text = "Scanning project..."
        scanSummaryLabel.foreground = Color(0xFB, 0xBF, 0x24)
        brokenBannerPanel.isVisible = false
        scanTopPanel.revalidate()
        scanTopPanel.repaint()
        scanTableModel.rowCount = 0
        scanTableModel.addRow(arrayOf("Scanning...", "", "", ""))

        Thread {
            val json = pythonRunner.runScanner(projectRoot)
            com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                scanTableModel.rowCount = 0
                parseAndFillScanResults(json)
                onScanFinishedCallbacks(projectRoot)
            }
        }.start()
    }

    private fun onTokenSelected(tokenName: String) {
        onTokenSelectedCallback(tokenName)

        Thread {
            val siblingsJson = pythonRunner.getTokenSiblings(tokenName)
            SwingUtilities.invokeLater {
                try {
                    val cleanJson = BridgeUiUtils.extractJson(siblingsJson)
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
                                siblingsPanel.add(JLabel(",").apply { foreground = BridgeColors.textMuted })
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
            val cleanJson = BridgeUiUtils.extractJson(json)
            val root = gson.fromJson(cleanJson, JsonObject::class.java)
            val registered = root.getAsJsonArray("registered_tokens")
            val hardcoded = root.getAsJsonArray("hardcoded_values")
            val brokenFiles = when {
                root.has("broken_files") && root.get("broken_files").isJsonArray -> root.getAsJsonArray("broken_files")
                root.has("report") && root.getAsJsonObject("report").has("broken_files") -> root.getAsJsonObject("report").getAsJsonArray("broken_files")
                else -> null
            }

            val regCount = registered?.size() ?: 0
            val hardCount = hardcoded?.size() ?: 0

            activeBrokenFiles.clear()
            if (brokenFiles != null) {
                for (elem in brokenFiles) {
                    val bObj = elem.asJsonObject
                    val fPath = bObj.get("full_path")?.asString ?: bObj.get("file")?.asString ?: ""
                    if (fPath.isNotBlank()) {
                        activeBrokenFiles[fPath] = bObj
                    }
                }
            }
            updateBrokenFilesUI()

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

            scanSummaryLabel.text = "Found $regCount tokens, $hardCount hardcoded values"
            scanSummaryLabel.foreground = BridgeColors.statusGreen
        } catch (e: Exception) {
            scanSummaryLabel.text = "Scan error: ${e.message}"
            scanSummaryLabel.foreground = Color(0xF8, 0x71, 0x71)
            scanTableModel.addRow(arrayOf("Error", e.message ?: "", "", ""))
            brokenBannerPanel.isVisible = false
            brokenBannerPanel.revalidate()
            brokenBannerPanel.repaint()
            scanTopPanel.revalidate()
            scanTopPanel.repaint()
        }
    }

    fun runSingleFileSyntaxCheck(filePath: String) {
        try {
            com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                com.intellij.openapi.fileEditor.FileDocumentManager.getInstance().saveAllDocuments()
            }
            Thread.sleep(120)

            val jsonStr = pythonRunner.checkSyntaxFile(filePath)
            val clean = BridgeUiUtils.extractJson(jsonStr)
            val obj = gson.fromJson(clean, JsonObject::class.java) ?: return
            val isValid = obj.get("is_valid")?.asBoolean ?: true

            com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                val pRoot = project.basePath ?: ""
                val relPath = try {
                    File(filePath).relativeTo(File(pRoot)).path.replace('\\', '/')
                } catch (e: Exception) {
                    File(filePath).name
                }

                if (!isValid) {
                    val line = obj.get("line")?.asInt ?: 1
                    val error = obj.get("error")?.asString ?: "Syntax Error"
                    val brokenObj = JsonObject().apply {
                        addProperty("file", relPath)
                        addProperty("line", line)
                        addProperty("error", error)
                        addProperty("full_path", filePath)
                    }
                    activeBrokenFiles[filePath] = brokenObj
                } else {
                    activeBrokenFiles.remove(filePath)
                }

                updateBrokenFilesUI()
            }
        } catch (e: Exception) {
            // ignore
        }
    }

    private fun updateBrokenFilesUI() {
        val brokenArray = com.google.gson.JsonArray()
        for (item in activeBrokenFiles.values) {
            brokenArray.add(item)
        }
        currentBrokenFiles = brokenArray
        val count = brokenArray.size()
        if (count > 0) {
            val first = brokenArray.get(0).asJsonObject
            val fileName = first.get("file")?.asString ?: ""
            val line = first.get("line")?.asInt ?: 1
            if (count == 1) {
                brokenWarningLabel.text = "Syntax error in $fileName (Line $line)!"
            } else {
                brokenWarningLabel.text = "Detected $count broken files with syntax errors!"
            }
            brokenBannerPanel.isVisible = true
        } else {
            brokenBannerPanel.isVisible = false
        }
        brokenBannerPanel.revalidate()
        brokenBannerPanel.repaint()
        scanTopPanel.revalidate()
        scanTopPanel.repaint()
    }

    private fun showBrokenFilesDialog() {
        val files = currentBrokenFiles
        if (files == null || files.size() == 0) {
            Messages.showInfoMessage(project, "No files with syntax errors found.", "Project Health")
            return
        }

        val dialog = JDialog(
            SwingUtilities.getWindowAncestor(this),
            "Broken Files with Syntax Errors",
            Dialog.ModalityType.APPLICATION_MODAL
        )
        dialog.setSize(750, 420)
        dialog.setLocationRelativeTo(null)

        val contentPanel = JPanel(BorderLayout(10, 10)).apply {
            background = BridgeColors.bgMain
            border = BorderFactory.createEmptyBorder(12, 12, 12, 12)
        }

        val headerLabel = JLabel("Detected ${files.size()} file(s) with syntax errors:").apply {
            foreground = Color(0xF8, 0x71, 0x71)
            font = Font("Segoe UI", Font.BOLD, 13)
        }
        contentPanel.add(headerLabel, BorderLayout.NORTH)

        val brokenModel = DefaultTableModel(arrayOf("File", "Line", "Error Message"), 0)
        val brokenTable = JBTable(brokenModel)
        BridgeUiUtils.styleTable(brokenTable)

        for (elem in files) {
            val obj = elem.asJsonObject
            val file = obj.get("file")?.asString ?: ""
            val line = obj.get("line")?.asInt ?: 1
            val error = obj.get("error")?.asString ?: ""
            brokenModel.addRow(arrayOf(file, line.toString(), error))
        }

        contentPanel.add(JBScrollPane(brokenTable), BorderLayout.CENTER)

        val bottomPanel = JPanel(FlowLayout(FlowLayout.RIGHT)).apply { background = BridgeColors.bgMain }
        val openButton = BridgeUiUtils.createStyledButton("Open in Editor", BridgeColors.accentBlue, Color.WHITE)
        openButton.addActionListener {
            val row = brokenTable.selectedRow
            if (row >= 0 && row < files.size()) {
                val obj = files.get(row).asJsonObject
                val relPath = obj.get("file")?.asString ?: ""
                val fullPath = obj.get("full_path")?.asString ?: ""
                val line = obj.get("line")?.asInt ?: 1

                val projectRoot = project.basePath ?: ""
                val targetPath = if (fullPath.isNotBlank()) fullPath else "$projectRoot/$relPath"
                val vFile = com.intellij.openapi.vfs.LocalFileSystem.getInstance().findFileByPath(targetPath)
                if (vFile != null) {
                    com.intellij.openapi.fileEditor.OpenFileDescriptor(
                        project, vFile, (line - 1).coerceAtLeast(0), 0
                    ).navigate(true)
                    dialog.dispose()
                } else {
                    Messages.showWarningDialog("Could not find file: $targetPath", "ComposeBridge")
                }
            } else {
                Messages.showInfoMessage("Please select a file from the list first.", "ComposeBridge")
            }
        }
        val closeButton = BridgeUiUtils.createStyledButton("Close", BridgeColors.btnGray, Color.WHITE)
        closeButton.addActionListener { dialog.dispose() }

        bottomPanel.add(openButton)
        bottomPanel.add(closeButton)
        contentPanel.add(bottomPanel, BorderLayout.SOUTH)

        dialog.contentPane = contentPanel
        dialog.isVisible = true
    }
}

