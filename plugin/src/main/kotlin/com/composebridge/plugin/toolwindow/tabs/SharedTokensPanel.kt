package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.models.SharedToken
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
import java.awt.Color
import java.awt.Font
import javax.swing.*
import javax.swing.table.DefaultTableModel

class SharedTokensPanel(
    private val project: Project,
    private val pythonRunner: PythonRunner
) : JPanel(BorderLayout()) {

    private val gson = Gson()

    val sharedTokensTableModel = object : DefaultTableModel(
        arrayOf("Token", "Value", "Usage"), 0
    ) {
        override fun isCellEditable(row: Int, column: Int): Boolean = false
    }
    val sharedTokensTable = JBTable(sharedTokensTableModel)
    val sharedTokensList = mutableListOf<SharedToken>()

    init {
        background = BridgeColors.bgMain
        border = BorderFactory.createMatteBorder(1, 0, 0, 0, BridgeColors.bgHeader)
        BridgeUiUtils.styleTable(sharedTokensTable)

        val sharedHeaderPanel = JPanel(BorderLayout()).apply {
            background = BridgeColors.bgDark
            border = BorderFactory.createEmptyBorder(6, 16, 6, 16)
        }
        val sharedTitle = JLabel("Shared Tokens Across Multiple Files").apply {
            foreground = BridgeColors.accentBlue
            font = Font("Segoe UI", Font.BOLD, 12)
        }
        val splitSelectedBtn = BridgeUiUtils.createStyledButton("Split", BridgeColors.btnGreen, Color.WHITE)
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
        add(sharedHeaderPanel, BorderLayout.NORTH)
        add(JBScrollPane(sharedTokensTable).apply { border = BorderFactory.createEmptyBorder() }, BorderLayout.CENTER)
    }

    fun refreshSharedTokens() {
        Thread {
            val json = pythonRunner.listTokens(project.basePath)
            SwingUtilities.invokeLater {
                try {
                    val root = gson.fromJson(BridgeUiUtils.extractJson(json), JsonObject::class.java)
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
}

