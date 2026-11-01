package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.table.JBTable
import java.awt.BorderLayout
import java.awt.Dimension
import java.awt.FlowLayout
import java.awt.Font
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent
import javax.swing.*
import javax.swing.table.DefaultTableModel

/**
 * Discovery Tab Panel.
 * Displays universal design token scatter analysis across the project,
 * provides design system file mapping input, and lists candidate registries.
 */
class DiscoveryTabPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner,
    private val openFileAtLine: (String, Int) -> Unit = { file, line ->
        BridgeUiUtils.openFileAtLine(project, file, line)
    }
) : JPanel(BorderLayout(0, 8)) {

    private val gson = Gson()
    private var isAnalyzing = false

    // Top: Design System Path Configuration Panel
    val pathField = JTextField(30).apply {
        toolTipText = "Enter relative or absolute path to your design system file (e.g. composeApp/src/.../DesignSystem.kt)"
    }

    val addPathButton = JButton("Add Path").apply {
        toolTipText = "Save this path as the primary design system file in .composebridge/config.json"
    }

    val currentMappingLabel = JLabel("Configured: None").apply {
        font = Font("Segoe UI", Font.PLAIN, 11)
        foreground = BridgeColors.textMuted
    }

    // Center: Scatter Results Table
    val scatterTitleLabel = JLabel("Discovered Design Tokens Scatter").apply {
        font = Font("Segoe UI", Font.BOLD, 13)
        foreground = BridgeColors.textPrimary
    }

    val refreshButton = JButton("Refresh Scatter").apply {
        toolTipText = "Re-scan the codebase for scattered tokens and candidate registries"
    }

    val statusSummaryLabel = JLabel("Click 'Refresh Scatter' to analyze scattered tokens.").apply {
        font = Font("Segoe UI", Font.PLAIN, 12)
        foreground = BridgeColors.textMuted
    }

    val scatterTableModel = object : DefaultTableModel(
        arrayOf("File", "Colors", "Dimensions", "Strings", "Total Tokens", "Candidate Registry"), 0
    ) {
        override fun isCellEditable(row: Int, column: Int): Boolean = false
    }

    val scatterTable = JBTable(scatterTableModel)

    init {
        background = BridgeColors.bgMain
        border = BorderFactory.createEmptyBorder(8, 10, 8, 10)

        // 1. Top Section: Mapping Panel
        val topContainer = JPanel(BorderLayout(0, 4)).apply {
            isOpaque = false
            border = BorderFactory.createCompoundBorder(
                BorderFactory.createMatteBorder(0, 0, 1, 0, BridgeColors.bgHeader),
                BorderFactory.createEmptyBorder(0, 0, 8, 0)
            )

            val inputRow = JPanel(FlowLayout(FlowLayout.LEFT, 8, 2)).apply {
                isOpaque = false
                add(JLabel("Design System Path:").apply {
                    font = Font("Segoe UI", Font.BOLD, 12)
                    foreground = BridgeColors.textPrimary
                })
                add(pathField)
                add(addPathButton)
            }

            val statusRow = JPanel(FlowLayout(FlowLayout.LEFT, 8, 0)).apply {
                isOpaque = false
                add(currentMappingLabel)
            }

            add(inputRow, BorderLayout.NORTH)
            add(statusRow, BorderLayout.SOUTH)
        }

        // 2. Center Section: Header + Table
        val centerHeader = JPanel(BorderLayout()).apply {
            isOpaque = false
            val leftTitle = JPanel(FlowLayout(FlowLayout.LEFT, 0, 4)).apply {
                isOpaque = false
                add(scatterTitleLabel)
            }
            val rightButtons = JPanel(FlowLayout(FlowLayout.RIGHT, 4, 0)).apply {
                isOpaque = false
                add(refreshButton)
            }
            add(leftTitle, BorderLayout.WEST)
            add(rightButtons, BorderLayout.EAST)
        }

        BridgeUiUtils.styleTable(scatterTable)

        // Column widths
        scatterTable.columnModel.getColumn(0).preferredWidth = 320
        scatterTable.columnModel.getColumn(1).preferredWidth = 60
        scatterTable.columnModel.getColumn(2).preferredWidth = 80
        scatterTable.columnModel.getColumn(3).preferredWidth = 60
        scatterTable.columnModel.getColumn(4).preferredWidth = 80
        scatterTable.columnModel.getColumn(5).preferredWidth = 120

        // Double click to open file
        scatterTable.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                if (e.clickCount == 2) {
                    val row = scatterTable.rowAtPoint(e.point)
                    if (row >= 0 && row < scatterTableModel.rowCount) {
                        val file = scatterTableModel.getValueAt(row, 0) as? String ?: ""
                        if (file.isNotBlank()) {
                            openFileAtLine(file, 1)
                        }
                    }
                }
            }
        })

        val centerPanel = JPanel(BorderLayout(0, 6)).apply {
            isOpaque = false
            add(centerHeader, BorderLayout.NORTH)
            add(JBScrollPane(scatterTable), BorderLayout.CENTER)
            add(statusSummaryLabel, BorderLayout.SOUTH)
        }

        add(topContainer, BorderLayout.NORTH)
        add(centerPanel, BorderLayout.CENTER)

        // Listeners
        addPathButton.addActionListener { onAddPath() }
        refreshButton.addActionListener { refreshScatter() }

        // Initial mapping load
        loadCurrentMappings()
    }

    private fun onAddPath() {
        val inputPath = pathField.text.trim()
        if (inputPath.isBlank()) {
            Messages.showWarningDialog("Please enter or paste a valid design system file path.", "Discovery")
            return
        }

        addPathButton.isEnabled = false
        Thread {
            try {
                val json = pythonRunner.setDesignFileMapping("all", inputPath)
                SwingUtilities.invokeLater {
                    addPathButton.isEnabled = true
                    try {
                        val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
                        if (root.get("success")?.asBoolean == true) {
                            val mapped = root.get("mapped_file")?.asString ?: inputPath
                            currentMappingLabel.text = "Configured: $mapped"
                            currentMappingLabel.foreground = BridgeColors.statusGreen
                            Messages.showInfoMessage("Design system path configured successfully:\n$mapped", "Discovery Mapping")
                        } else {
                            val err = root.get("error")?.asString ?: "Failed to save mapping."
                            Messages.showErrorDialog(err, "Discovery Mapping Error")
                        }
                    } catch (e: Exception) {
                        Messages.showErrorDialog("Error parsing response: ${e.message}", "Discovery Error")
                    }
                }
            } catch (e: Exception) {
                SwingUtilities.invokeLater {
                    addPathButton.isEnabled = true
                    Messages.showErrorDialog("Execution error: ${e.message}", "Discovery Error")
                }
            }
        }.start()
    }

    fun loadCurrentMappings() {
        Thread {
            try {
                val json = pythonRunner.getDesignFileMappings()
                val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
                val mappings = root.getAsJsonObject("mappings")
                val colorMap = mappings?.get("color")?.asString
                val allMap = colorMap ?: mappings?.get("all")?.asString
                SwingUtilities.invokeLater {
                    if (!allMap.isNullOrBlank()) {
                        pathField.text = allMap
                        currentMappingLabel.text = "Configured: $allMap"
                        currentMappingLabel.foreground = BridgeColors.statusGreen
                    } else {
                        currentMappingLabel.text = "Configured: None (using automatic heuristic detection)"
                        currentMappingLabel.foreground = BridgeColors.textMuted
                    }
                }
            } catch (_: Exception) {
            }
        }.start()
    }

    fun refreshScatter() {
        if (isAnalyzing) return
        isAnalyzing = true
        refreshButton.isEnabled = false
        statusSummaryLabel.text = "Scanning project for scattered design tokens..."
        statusSummaryLabel.foreground = BridgeColors.textMuted

        Thread {
            try {
                val json = pythonRunner.analyzeDesignScatter()
                SwingUtilities.invokeLater {
                    isAnalyzing = false
                    refreshButton.isEnabled = true
                    parseAndFillScatter(json)
                }
            } catch (e: Exception) {
                SwingUtilities.invokeLater {
                    isAnalyzing = false
                    refreshButton.isEnabled = true
                    statusSummaryLabel.text = "Error scanning scatter: ${e.message}"
                    statusSummaryLabel.foreground = BridgeColors.badgeRed
                }
            }
        }.start()
    }

    private fun parseAndFillScatter(json: String) {
        try {
            val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
            if (root.get("success")?.asBoolean != true) {
                val err = root.get("error")?.asString ?: "Failed to analyze scatter."
                statusSummaryLabel.text = "Error: $err"
                statusSummaryLabel.foreground = BridgeColors.badgeRed
                return
            }

            scatterTableModel.rowCount = 0

            val summary = root.getAsJsonObject("summary")
            val totalFiles = summary?.get("files_with_tokens")?.asInt ?: 0
            val totalColors = summary?.get("total_colors")?.asInt ?: 0
            val totalDimens = summary?.get("total_dimensions")?.asInt ?: 0
            val totalStrings = summary?.get("total_strings")?.asInt ?: 0

            val recommended = root.getAsJsonObject("recommended_registries")
            val colorRecs = recommended?.getAsJsonArray("color")?.map { it.asString } ?: emptyList()
            val recNames = colorRecs.map { it.substringAfterLast("/") }.distinct().take(3).joinToString(", ")

            val scatterFiles = root.getAsJsonArray("scatter_files")
            if (scatterFiles != null) {
                for (elem in scatterFiles) {
                    val obj = elem.asJsonObject
                    val file = obj.get("file")?.asString ?: ""
                    val counts = obj.getAsJsonObject("counts")
                    val c = counts?.get("color")?.asInt ?: 0
                    val d = counts?.get("dimension")?.asInt ?: 0
                    val s = counts?.get("string")?.asInt ?: 0
                    val total = counts?.get("total")?.asInt ?: 0
                    val isCandidate = obj.get("is_candidate_registry")?.asBoolean == true
                    val candidateStr = if (isCandidate) "⭐ Candidate" else "Usage File"

                    scatterTableModel.addRow(arrayOf(
                        file,
                        c.toString(),
                        d.toString(),
                        s.toString(),
                        total.toString(),
                        candidateStr
                    ))
                }
            }

            statusSummaryLabel.text = "Files with tokens: $totalFiles | Colors: $totalColors | Dimensions: $totalDimens | Strings: $totalStrings | Recommended: ${if (recNames.isNotBlank()) recNames else "None"}"
            statusSummaryLabel.foreground = BridgeColors.textPrimary

            loadCurrentMappings()
        } catch (e: Exception) {
            statusSummaryLabel.text = "Error displaying results: ${e.message}"
            statusSummaryLabel.foreground = BridgeColors.badgeRed
        }
    }
}

