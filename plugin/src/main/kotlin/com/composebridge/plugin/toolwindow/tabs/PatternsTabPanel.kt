package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.ui.components.JBScrollPane
import java.awt.*
import javax.swing.*
import javax.swing.table.DefaultTableModel

class PatternsTabPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner,
    private val onPatternsModified: () -> Unit
) : JPanel(BorderLayout()) {

    private val gson = Gson()

    val patternTableModel = object : DefaultTableModel(
        arrayOf("Base Token", "Pattern", "Occurrences", "Suggested Token"), 0
    ) {
        override fun isCellEditable(row: Int, column: Int): Boolean = false
    }

    val patternTable = com.intellij.ui.table.JBTable(patternTableModel)
    val patternSummaryLabel = JLabel("Press 'Scan Project' to detect patterns").apply {
        foreground = Color(0x60, 0xA5, 0xFA)
        font = Font("Segoe UI", Font.BOLD, 13)
        border = BorderFactory.createEmptyBorder(10, 16, 10, 16)
    }

    val patternIds = mutableListOf<String>()
    var selectedPatternId: String? = null

    init {
        background = BridgeColors.bgMain
        BridgeUiUtils.styleTable(patternTable)

        val patternPanel = JPanel(BorderLayout()).apply { background = BridgeColors.bgMain }
        patternPanel.add(patternSummaryLabel, BorderLayout.NORTH)
        patternPanel.add(JBScrollPane(patternTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)

        val patternBottom = JPanel(FlowLayout(FlowLayout.LEFT, 12, 10)).apply {
            background = BridgeColors.bgTabBar
            border = BorderFactory.createEmptyBorder(4, 8, 4, 8)
        }
        val replaceButton = BridgeUiUtils.createStyledButton("Replace Pattern", BridgeColors.accentBlue, Color.WHITE)
        replaceButton.addActionListener { onReplacePattern() }
        patternBottom.add(replaceButton)

        val rollbackButton = BridgeUiUtils.createStyledButton("Rollback Pattern", BridgeColors.btnRollback, Color.WHITE)
        rollbackButton.addActionListener { onRollbackPattern() }
        patternBottom.add(rollbackButton)

        add(patternPanel, BorderLayout.CENTER)
        add(patternBottom, BorderLayout.SOUTH)

        // Select row in Patterns Table
        patternTable.selectionModel.addListSelectionListener { event ->
            if (!event.valueIsAdjusting) {
                val row = patternTable.selectedRow
                if (row >= 0 && row < patternIds.size) {
                    selectedPatternId = patternIds[row]
                }
            }
        }
    }

    fun refreshPatterns(projectRoot: String) {
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
            val cleanJson = BridgeUiUtils.extractJson(json)
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

            Make sure you have committed your changes to git first.

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
            val cleanJson = BridgeUiUtils.extractJson(json)
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
                onPatternsModified()
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
                    val cleanJson = BridgeUiUtils.extractJson(json)
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
                        onPatternsModified()
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

