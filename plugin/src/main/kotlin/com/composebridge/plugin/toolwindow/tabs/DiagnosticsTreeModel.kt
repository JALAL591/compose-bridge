package com.composebridge.plugin.toolwindow.tabs

import com.intellij.ui.treeStructure.treetable.TreeTableModel
import javax.swing.JTree
import javax.swing.tree.DefaultMutableTreeNode
import javax.swing.tree.DefaultTreeModel
import javax.swing.tree.TreePath

/**
 * Node representing a source file with its aggregated issues count.
 */
class FileNode(
    val fileName: String,
    val relativePath: String,
    var errorsCount: Int = 0,
    var warningsCount: Int = 0
) : DefaultMutableTreeNode() {

    override fun toString(): String {
        return fileName
    }

    fun getIssueNodes(): List<IssueNode> {
        val list = mutableListOf<IssueNode>()
        for (i in 0 until childCount) {
            val child = getChildAt(i) as? IssueNode
            if (child != null) list.add(child)
        }
        return list
    }
}

/**
 * Node representing a specific diagnostic issue (Error, Warning, Weak Warning, Info).
 */
class IssueNode(
    val file: String,
    val relativePath: String,
    val line: Int,
    val column: Int,
    val severity: String,
    val message: String,
    val inspectionId: String = ""
) : DefaultMutableTreeNode() {

    override fun toString(): String = "\u21B3 Line $line"
}

/**
 * TreeTableModel for Diagnostics TreeTable.
 * Groups findings hierarchically by file.
 * Each file row shows its file name and total count at the end.
 * Clicking a file row expands/collapses its issues downwards.
 */
class DiagnosticsTreeModel(
    val rootNode: DefaultMutableTreeNode = DefaultMutableTreeNode("Root")
) : DefaultTreeModel(rootNode), TreeTableModel {

    private var tree: JTree? = null
    val fileNodeMap = LinkedHashMap<String, FileNode>()

    override fun setTree(tree: JTree?) {
        this.tree = tree
    }

    override fun getColumnCount(): Int = 5

    override fun getColumnName(column: Int): String {
        return when (column) {
            0 -> "File / Location"
            1 -> "Line"
            2 -> "Severity"
            3 -> "Message"
            4 -> "AI Action"
            else -> ""
        }
    }

    override fun getColumnClass(column: Int): Class<*> {
        return if (column == 0) TreeTableModel::class.java else String::class.java
    }

    override fun getValueAt(node: Any?, column: Int): Any? {
        return when (node) {
            is FileNode -> {
                when (column) {
                    0 -> node
                    1 -> ""
                    2 -> if (node.errorsCount > 0) "ERROR" else "WARNING"
                    3 -> {
                        val total = node.errorsCount + node.warningsCount
                        if (node.errorsCount > 0 && node.warningsCount > 0) {
                            "${node.errorsCount} Error(s), ${node.warningsCount} Warning(s) ($total total)"
                        } else if (node.errorsCount > 0) {
                            "${node.errorsCount} Error(s)"
                        } else {
                            "${node.warningsCount} Warning(s)"
                        }
                    }
                    4 -> "AI_ACTION"
                    else -> ""
                }
            }
            is IssueNode -> {
                when (column) {
                    0 -> node
                    1 -> node.line.toString()
                    2 -> node.severity
                    3 -> node.message
                    4 -> ""
                    else -> ""
                }
            }
            else -> ""
        }
    }

    override fun isCellEditable(node: Any?, column: Int): Boolean = false

    override fun setValueAt(value: Any?, node: Any?, column: Int) {}

    fun clear() {
        rootNode.removeAllChildren()
        fileNodeMap.clear()
        reload()
    }

    fun ensureRootExpanded() {
        tree?.let { t ->
            val rootPath = TreePath(rootNode)
            if (!t.isExpanded(rootPath)) {
                t.expandPath(rootPath)
            }
        }
    }

    fun addOrUpdateFile(
        fileName: String,
        relativePath: String,
        errorsCount: Int,
        warningsCount: Int,
        diagnostics: List<com.composebridge.plugin.services.IdeDiagnosticsService.DiagnosticItem>
    ): FileNode? {
        if (diagnostics.isEmpty()) return null

        var fileNode = fileNodeMap[relativePath]
        if (fileNode == null) {
            fileNode = FileNode(fileName, relativePath, errorsCount, warningsCount)
            fileNodeMap[relativePath] = fileNode
            rootNode.add(fileNode)

            for (d in diagnostics) {
                val issueNode = IssueNode(
                    file = fileName,
                    relativePath = relativePath,
                    line = d.line,
                    column = d.column,
                    severity = d.severity,
                    message = d.message,
                    inspectionId = d.inspectionId
                )
                fileNode.add(issueNode)
            }
            nodesWereInserted(rootNode, intArrayOf(rootNode.childCount - 1))
        } else {
            fileNode.removeAllChildren()
            fileNode.errorsCount = errorsCount
            fileNode.warningsCount = warningsCount

            for (d in diagnostics) {
                val issueNode = IssueNode(
                    file = fileName,
                    relativePath = relativePath,
                    line = d.line,
                    column = d.column,
                    severity = d.severity,
                    message = d.message,
                    inspectionId = d.inspectionId
                )
                fileNode.add(issueNode)
            }
            nodeStructureChanged(fileNode)
        }
        ensureRootExpanded()
        return fileNode
    }
}