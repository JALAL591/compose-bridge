package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.AgentPromptBuilder
import com.composebridge.plugin.services.FeatureGateService
import com.composebridge.plugin.services.IdeDiagnosticsService
import com.composebridge.plugin.ui.components.BridgeColors
import com.google.gson.JsonObject
import com.intellij.openapi.project.Project
import com.intellij.ui.treeStructure.treetable.TreeTable
import java.awt.*
import java.awt.datatransfer.StringSelection
import java.awt.event.MouseEvent
import java.io.File
import javax.swing.*
import javax.swing.table.TableCellRenderer

/**
 * TableCellRenderer and click dispatcher for the "AI Action" column.
 * Renders [📋 Copy] and [🚀 Auto-Fix] buttons for FileNode rows.
 */
class DiagnosticsAiActionRenderer : TableCellRenderer {

    private val containerPanel = JPanel(FlowLayout(FlowLayout.CENTER, 4, 1)).apply {
        isOpaque = true
    }

    private val copyLabel = JLabel("📋 Copy").apply {
        font = Font("Segoe UI", Font.BOLD, 10)
        foreground = Color(0x60, 0xA5, 0xFA)
        border = BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(Color(0x3B, 0x82, 0xF6), 1, true),
            BorderFactory.createEmptyBorder(1, 5, 1, 5)
        )
        toolTipText = "Copy AI prompt with all issues to clipboard"
    }

    private val fixLabel = JLabel("🚀 Auto-Fix").apply {
        font = Font("Segoe UI", Font.BOLD, 10)
        foreground = Color(0xF5, 0x9E, 0x0B)
        border = BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(Color(0xD9, 0x77, 0x06), 1, true),
            BorderFactory.createEmptyBorder(1, 5, 1, 5)
        )
        toolTipText = "Automatically fix issues via ComposeBridge Agent & MCP"
    }

    private val emptyPanel = JPanel().apply { isOpaque = false }

    init {
        containerPanel.add(copyLabel)
        containerPanel.add(fixLabel)
    }

    override fun getTableCellRendererComponent(
        table: JTable?,
        value: Any?,
        isSelected: Boolean,
        hasFocus: Boolean,
        row: Int,
        column: Int
    ): Component {
        if (value != "AI_ACTION") {
            return emptyPanel
        }

        containerPanel.background = if (isSelected) {
            table?.selectionBackground ?: BridgeColors.bgDark
        } else {
            BridgeColors.bgDark
        }
        return containerPanel
    }

    companion object {
        /**
         * Dispatches click events inside the "AI Action" column to either Copy Prompt or Auto-Fix.
         */
        fun handleCellClick(
            project: Project,
            treeTable: TreeTable,
            e: MouseEvent,
            notify: (String) -> Unit
        ) {
            val row = treeTable.rowAtPoint(e.point)
            if (row < 0) return
            val path = treeTable.tree.getPathForRow(row) ?: return
            val fileNode = path.lastPathComponent as? FileNode ?: return

            val col = treeTable.columnAtPoint(e.point)
            if (col < 0) return
            val rect = treeTable.getCellRect(row, col, false)
            val relX = e.x - rect.x

            val issueNodes = fileNode.getIssueNodes()
            val issues = issueNodes.map { node ->
                IdeDiagnosticsService.DiagnosticItem(
                    line = node.line,
                    column = node.column,
                    severity = node.severity,
                    message = node.message,
                    inspectionId = node.inspectionId
                )
            }

            if (issues.isEmpty()) {
                notify("No diagnostic issues in ${fileNode.fileName}")
                return
            }

            val gate = FeatureGateService.getInstance(project)

            if (relX < rect.width / 2) {
                // Copy Prompt
                if (!gate.canUseFreeCopy()) {
                    notify("Free copy quota reached.")
                    return
                }

                val prompt = AgentPromptBuilder.buildFixPrompt(fileNode.fileName, fileNode.relativePath, issues)
                val sel = StringSelection(prompt)
                Toolkit.getDefaultToolkit().systemClipboard.setContents(sel, sel)
                notify("📋 Copied AI fix prompt for ${fileNode.fileName} (${issues.size} issues) to clipboard!")
            } else {
                // Auto-Fix via MCP / WebSocket
                if (!gate.canUseProFix()) {
                    notify("Auto-Fix is currently disabled.")
                    return
                }

                val basePath = project.basePath ?: ""
                val json = AgentPromptBuilder.buildFixRequestJson(basePath, fileNode.fileName, fileNode.relativePath, issues)

                try {
                    val dotDir = File(basePath, ".composebridge")
                    if (!dotDir.exists()) dotDir.mkdirs()
                    val reqFile = File(dotDir, "mcp_fix_request.json")
                    reqFile.writeText(json)
                } catch (_: Exception) {}

                val payload = JsonObject().apply {
                    addProperty("type", "mcp_fix_request")
                    addProperty("file", fileNode.fileName)
                    addProperty("relativePath", fileNode.relativePath)
                    addProperty("issuesCount", issues.size)
                }
                val sent = IdeDiagnosticsService.sendWebSocketMessage(payload)
                val wsText = if (sent) "dispatched to Agent via WebSocket" else "saved to .composebridge/mcp_fix_request.json"
                notify("🚀 Auto-Fix dispatched for ${fileNode.fileName} ($wsText)")
            }
        }
    }
}
