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
import java.awt.event.MouseAdapter
import java.awt.event.MouseEvent
import javax.swing.*
import javax.swing.table.DefaultTableModel

class ImpactTabPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner,
    private val openFileAtLine: (String, Int) -> Unit
) : JPanel(BorderLayout()) {

    private val gson = Gson()

    val impactTitleLabel = JLabel("Select a token from Scan tab to see impact").apply {
        foreground = BridgeColors.textPrimary
        font = Font("Segoe UI", Font.BOLD, 12)
    }

    val impactSummaryLabel = JLabel(" ").apply {
        foreground = BridgeColors.textMuted
        font = Font("Segoe UI", Font.PLAIN, 12)
    }

    val impactTableModel = object : DefaultTableModel(
        arrayOf("File", "Line", "Content", "Composable"), 0
    ) {
        override fun isCellEditable(row: Int, column: Int): Boolean = false
    }

    val impactTable = JBTable(impactTableModel)

    init {
        background = BridgeColors.bgMain
        BridgeUiUtils.styleTable(impactTable)

        impactTable.addMouseListener(object : MouseAdapter() {
            override fun mouseClicked(e: MouseEvent) {
                if (e.clickCount == 2) {
                    val row = impactTable.rowAtPoint(e.point)
                    if (row >= 0 && row < impactTableModel.rowCount) {
                        val file = impactTableModel.getValueAt(row, 0) as? String ?: ""
                        val line = (impactTableModel.getValueAt(row, 1) as? Int)
                            ?: (impactTableModel.getValueAt(row, 1) as? String)?.toIntOrNull()
                            ?: 1
                        if (file.isNotBlank()) {
                            openFileAtLine(file, line)
                        }
                    }
                }
            }
        })

        val impactTop = JPanel(BorderLayout()).apply {
            background = BridgeColors.bgDark
            border = BorderFactory.createEmptyBorder(6, 12, 6, 12)
        }
        impactTop.add(impactTitleLabel, BorderLayout.NORTH)
        impactTop.add(impactSummaryLabel, BorderLayout.SOUTH)
        add(impactTop, BorderLayout.NORTH)
        add(JBScrollPane(impactTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
    }

    fun loadImpact(tokenName: String) {
        impactTitleLabel.text = "Impact: $tokenName"
        impactSummaryLabel.text = "Loading..."
        impactTableModel.rowCount = 0

        Thread {
            val json = pythonRunner.getTokenImpact(tokenName)
            SwingUtilities.invokeLater {
                parseAndFillImpactResults(json, tokenName)
            }
        }.start()
    }

    private fun parseAndFillImpactResults(json: String, tokenName: String) {
        try {
            val cleanJson = BridgeUiUtils.extractJson(json)
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
}

