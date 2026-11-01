package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.PythonRunner
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.openapi.project.Project
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.table.JBTable
import java.awt.BorderLayout
import java.awt.Font
import javax.swing.*
import javax.swing.table.DefaultTableModel

class SplitTabPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner
) : JPanel(BorderLayout()) {

    private val gson = Gson()

    val splitTableModel = object : DefaultTableModel(
        arrayOf("Token", "Value", "Contexts", "Suggested Tokens"), 0
    ) {
        override fun isCellEditable(row: Int, column: Int): Boolean = false
    }

    val splitTable = JBTable(splitTableModel)

    val splitSummaryLabel = JLabel("Press 'Scan Project' to see split suggestions").apply {
        foreground = BridgeColors.statusGreen
        font = Font("Segoe UI", Font.BOLD, 13)
        border = BorderFactory.createEmptyBorder(10, 16, 10, 16)
    }

    init {
        background = BridgeColors.bgMain
        BridgeUiUtils.styleTable(splitTable)
        add(splitSummaryLabel, BorderLayout.NORTH)
        add(JBScrollPane(splitTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
    }

    fun refreshSplitSuggestions(projectRoot: String) {
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
            val cleanJson = BridgeUiUtils.extractJson(json)
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
}

