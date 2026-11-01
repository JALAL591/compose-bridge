package com.composebridge.plugin.ui.components

import com.intellij.openapi.fileEditor.OpenFileDescriptor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VfsUtil
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.ui.table.JBTable
import java.awt.*
import java.io.File
import javax.swing.*
import javax.swing.JTable
import javax.swing.table.DefaultTableCellRenderer

object BridgeUiUtils {

    fun createStyledButton(text: String, bg: Color, fg: Color = Color.WHITE, radius: Int = 5): JButton {
        val btn = object : JButton(text) {
            override fun paintComponent(g: Graphics) {
                val g2 = g.create() as Graphics2D
                g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON)
                val fill = if (model.isPressed) bg.darker() else if (model.isRollover) bg.brighter() else bg
                g2.color = fill
                g2.fillRoundRect(0, 0, width, height, radius * 2, radius * 2)
                g2.dispose()
                super.paintComponent(g)
            }
        }
        btn.isContentAreaFilled = false
        btn.isFocusPainted = false
        btn.isBorderPainted = false
        btn.foreground = fg
        btn.font = Font("Segoe UI", Font.BOLD, 11)
        btn.cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
        btn.border = BorderFactory.createEmptyBorder(4, 10, 4, 10)
        return btn
    }

    fun styleTable(table: JBTable) {
        table.rowHeight = 36
        table.setShowGrid(false)
        table.intercellSpacing = Dimension(0, 2)
        table.background = BridgeColors.bgDark
        table.selectionBackground = BridgeColors.bgSelected
        table.selectionForeground = Color.WHITE
        table.font = Font("Segoe UI", Font.PLAIN, 12)

        val header = table.tableHeader
        header.preferredSize = Dimension(header.preferredSize.width, 34)
        header.background = BridgeColors.bgHeader
        header.foreground = BridgeColors.textPrimary
        header.font = Font("Segoe UI", Font.BOLD, 12)

        table.setDefaultRenderer(Any::class.java, object : DefaultTableCellRenderer() {
            override fun getTableCellRendererComponent(
                t: JTable, value: Any?, isSelected: Boolean, hasFocus: Boolean, row: Int, col: Int
            ): Component {
                val comp = super.getTableCellRendererComponent(t, value, isSelected, hasFocus, row, col) as JLabel
                comp.border = BorderFactory.createEmptyBorder(0, 14, 0, 14)
                if (isSelected) {
                    comp.background = BridgeColors.bgSelected
                    comp.foreground = Color.WHITE
                } else {
                    comp.background = if (row % 2 == 0) BridgeColors.bgDark else BridgeColors.bgRowAlt
                    comp.foreground = BridgeColors.textPrimary
                }
                return comp
            }
        })
    }

    fun extractJson(raw: String): String {
        val start = raw.indexOf('{')
        val end = raw.lastIndexOf('}')
        return if (start != -1 && end != -1 && end >= start) raw.substring(start, end + 1) else raw
    }

    fun openFileAtLine(project: Project, filePath: String, line: Int) {
        val projectRoot = project.basePath ?: return
        val targetName = File(filePath).name
        var foundFile: VirtualFile? = null

        val fullPath = if (File(filePath).isAbsolute) filePath else "$projectRoot/$filePath"
        val directVFile = LocalFileSystem.getInstance().findFileByPath(fullPath.replace("\\", "/"))
        if (directVFile != null && directVFile.exists()) {
            foundFile = directVFile
        } else {
            val rootVFile = LocalFileSystem.getInstance().findFileByPath(projectRoot) ?: return
            VfsUtil.processFilesRecursively(rootVFile) { vFile ->
                if (vFile == null || vFile.isDirectory) return@processFilesRecursively true
                val path = vFile.path
                if (path.contains("/build/") || path.contains("\\build\\")) return@processFilesRecursively true
                if (vFile.name == targetName) {
                    foundFile = vFile
                    return@processFilesRecursively false
                }
                true
            }
        }

        val vFile = foundFile ?: run {
            Messages.showWarningDialog("Could not find file '$filePath'", "ComposeBridge")
            return
        }

        val lineIndex = if (line > 0) line - 1 else 0
        OpenFileDescriptor(project, vFile, lineIndex, 0).navigate(true)
    }

    fun refreshVfsAndDocument(project: Project, filePath: String) {
        com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
            try {
                val pRoot = project.basePath ?: ""
                val fullPath = if (File(filePath).isAbsolute) filePath else File(pRoot, filePath).absolutePath
                val ioFile = File(fullPath)
                val lfs = LocalFileSystem.getInstance()
                val vf = lfs.refreshAndFindFileByIoFile(ioFile)
                if (vf != null) {
                    vf.refresh(false, false)
                    val fdm = com.intellij.openapi.fileEditor.FileDocumentManager.getInstance()
                    val doc = fdm.getCachedDocument(vf)
                    if (doc != null) {
                        fdm.reloadFromDisk(doc)
                    }
                } else {
                    lfs.refresh(false)
                }
            } catch (_: Exception) {}
        }
    }

    fun refreshAllVfsAndDocuments() {
        com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
            try {
                val lfs = LocalFileSystem.getInstance()
                lfs.refresh(false)
                val fdm = com.intellij.openapi.fileEditor.FileDocumentManager.getInstance()
                fdm.reloadFiles()
            } catch (_: Exception) {}
        }
    }
}
