package com.composebridge.plugin.toolwindow.tabs

import com.composebridge.plugin.services.IdeDiagnosticsService
import com.composebridge.plugin.ui.components.BridgeColors
import com.composebridge.plugin.ui.components.BridgeUiUtils
import com.intellij.ide.util.PropertiesComponent
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.popup.JBPopupFactory
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import java.awt.*
import javax.swing.*

/**
 * Filter Popup for IDE Diagnostics.
 * Displays checkboxes for discovered inspection types with real-time occurrence counts.
 * State is persistently stored per-project via PropertiesComponent.
 */
object DiagnosticsFilterPopup {

    private const val PREF_KEY_DISABLED = "composebridge.diagnostics.disabled_inspections"

    /**
     * Retrieves the set of inspection IDs that the user has unchecked.
     */
    fun getDisabledInspectionIds(project: Project): MutableSet<String> {
        val props = PropertiesComponent.getInstance(project)
        val raw = props.getValue(PREF_KEY_DISABLED, "")
        if (raw.isBlank()) return mutableSetOf()
        return raw.split("|||").filter { it.isNotBlank() }.toMutableSet()
    }

    /**
     * Persists the set of disabled inspection IDs to project properties.
     */
    fun setDisabledInspectionIds(project: Project, disabled: Set<String>) {
        val props = PropertiesComponent.getInstance(project)
        props.setValue(PREF_KEY_DISABLED, disabled.joinToString("|||"))
    }

    /**
     * Displays a styled native popup attached to the Filter button.
     */
    fun show(
        project: Project,
        anchor: Component,
        allItems: List<IdeDiagnosticsService.DiagnosticItem>,
        onFilterChanged: () -> Unit
    ) {
        val disabledIds = getDisabledInspectionIds(project)

        // Group items by inspectionId
        val counts = LinkedHashMap<String, Int>()
        for (item in allItems) {
            val id = item.inspectionId.trim().ifBlank { "Other" }
            counts[id] = (counts[id] ?: 0) + 1
        }

        if (counts.isEmpty()) {
            val emptyPanel = JPanel(BorderLayout()).apply {
                background = BridgeColors.bgDark
                border = BorderFactory.createEmptyBorder(16, 20, 16, 20)
                add(JBLabel("No diagnostic rules available yet. Run scan first.").apply {
                    foreground = BridgeColors.textMuted
                    font = Font("Segoe UI", Font.PLAIN, 12)
                })
            }
            JBPopupFactory.getInstance()
                .createComponentPopupBuilder(emptyPanel, null)
                .setTitle("Filter Inspections")
                .createPopup()
                .showUnderneathOf(anchor)
            return
        }

        // Sort: errors/highest occurrences first
        val sortedEntries = counts.entries.sortedByDescending { it.value }

        val checkboxes = mutableListOf<JBCheckBox>()
        val listPanel = JPanel().apply {
            layout = BoxLayout(this, BoxLayout.Y_AXIS)
            background = BridgeColors.bgDark
            border = BorderFactory.createEmptyBorder(8, 12, 8, 12)
        }

        for ((id, count) in sortedEntries) {
            val isEnabled = id !in disabledIds
            val cb = JBCheckBox("$id ($count)", isEnabled).apply {
                isOpaque = false
                foreground = BridgeColors.textPrimary
                font = Font("Segoe UI", Font.PLAIN, 12)
                cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
                alignmentX = Component.LEFT_ALIGNMENT
                border = BorderFactory.createEmptyBorder(3, 2, 3, 2)
                addActionListener {
                    if (isSelected) {
                        disabledIds.remove(id)
                    } else {
                        disabledIds.add(id)
                    }
                    setDisabledInspectionIds(project, disabledIds)
                    onFilterChanged()
                }
            }
            checkboxes.add(cb)
            listPanel.add(cb)
        }

        // Action bar: Select All / Deselect All
        val actionsPanel = JPanel(FlowLayout(FlowLayout.LEFT, 8, 4)).apply {
            background = BridgeColors.bgHeader
            border = BorderFactory.createCompoundBorder(
                BorderFactory.createMatteBorder(0, 0, 1, 0, Color(0x3C, 0x3F, 0x41)),
                BorderFactory.createEmptyBorder(4, 6, 4, 6)
            )

            val selectAllBtn = JButton("Select All").apply {
                font = Font("Segoe UI", Font.PLAIN, 11)
                isFocusable = false
                cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
                addActionListener {
                    disabledIds.clear()
                    checkboxes.forEach { it.isSelected = true }
                    setDisabledInspectionIds(project, disabledIds)
                    onFilterChanged()
                }
            }

            val deselectAllBtn = JButton("Deselect All").apply {
                font = Font("Segoe UI", Font.PLAIN, 11)
                isFocusable = false
                cursor = Cursor.getPredefinedCursor(Cursor.HAND_CURSOR)
                addActionListener {
                    sortedEntries.forEach { disabledIds.add(it.key) }
                    checkboxes.forEach { it.isSelected = false }
                    setDisabledInspectionIds(project, disabledIds)
                    onFilterChanged()
                }
            }

            add(selectAllBtn)
            add(deselectAllBtn)
        }

        val scrollPane = JBScrollPane(listPanel).apply {
            border = BorderFactory.createEmptyBorder()
            preferredSize = Dimension(340, 300.coerceAtMost(sortedEntries.size * 26 + 20))
            viewport.background = BridgeColors.bgDark
        }

        val rootPanel = JPanel(BorderLayout()).apply {
            background = BridgeColors.bgDark
            border = BorderFactory.createLineBorder(Color(0x3C, 0x3F, 0x41), 1)
            add(actionsPanel, BorderLayout.NORTH)
            add(scrollPane, BorderLayout.CENTER)
        }

        JBPopupFactory.getInstance()
            .createComponentPopupBuilder(rootPanel, null)
            .setTitle("Filter Inspections (${sortedEntries.size} rules)")
            .setMovable(true)
            .setResizable(true)
            .setRequestFocus(true)
            .createPopup()
            .showUnderneathOf(anchor)
    }
}