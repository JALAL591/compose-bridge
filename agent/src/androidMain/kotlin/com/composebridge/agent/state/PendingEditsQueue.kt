/**
 * ComposeBridge Pending Edits Queue.
 * إدارة طابور التعديلات المعلقة وتطبيقها التراجعي أو تأكيدها المجمّع.
 */
package com.composebridge.agent.state

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.composebridge.agent.BridgeTextRegistry
import com.composebridge.agent.BridgeThemeRegistry
import com.composebridge.agent.PendingEdit

object PendingEditsQueue {
    val pendingEdits = mutableStateListOf<PendingEdit>()
    val previewColors = mutableStateMapOf<String, String>()
    var syncInProgress: Boolean by mutableStateOf(false)
    var snackbarMessage: String? by mutableStateOf(null)
    var batchMessage: String? by mutableStateOf(null)

    val pendingCount: Int get() = pendingEdits.size

    fun showSnackbar(msg: String) {
        snackbarMessage = msg
    }

    fun addPendingEdit(edit: PendingEdit) {
        pendingEdits.removeAll { existing ->
            (existing.id == edit.id) ||
            (existing.file.isNotEmpty() && existing.file == edit.file && existing.line == edit.line &&
                (existing.property == edit.property || existing.property == "all" || edit.property == "all")) ||
            (existing.tokenName.isNotEmpty() && existing.tokenName == edit.tokenName && existing.property == edit.property)
        }
        pendingEdits.add(edit)
        if (edit.type == "text_edit") {
            val key = edit.refKey ?: edit.property.ifEmpty { edit.tokenName }
            BridgeTextRegistry.setOverride(key, edit.newValue)
            if (edit.property.isNotEmpty() && edit.property != key) {
                BridgeTextRegistry.setOverride(edit.property, edit.newValue)
            }
        } else {
            previewColors[edit.tokenName] = edit.newValue
            BridgeThemeRegistry.setColorHex(edit.tokenName, edit.newValue)
        }
    }

    fun removePendingEdit(id: String) {
        val edit = pendingEdits.find { it.id == id } ?: return
        pendingEdits.remove(edit)
        if (edit.type == "text_edit") {
            val key = edit.refKey ?: edit.property.ifEmpty { edit.tokenName }
            BridgeTextRegistry.setOverride(key, edit.oldValue)
            if (edit.property.isNotEmpty() && edit.property != key) {
                BridgeTextRegistry.setOverride(edit.property, edit.oldValue)
            }
        } else {
            previewColors.remove(edit.tokenName)
            BridgeThemeRegistry.setColorHex(edit.tokenName, edit.oldValue)
        }
    }

    fun onBatchAck(allReceivedIds: Set<String>) {
        pendingEdits.removeAll { it.id in allReceivedIds }
        if (pendingEdits.isEmpty()) {
            previewColors.clear()
        }
        syncInProgress = false
    }

    fun clearPendingEdits(revert: Boolean = true) {
        if (revert) {
            pendingEdits.forEach { edit ->
                if (edit.type == "text_edit") {
                    val key = edit.refKey ?: edit.property.ifEmpty { edit.tokenName }
                    BridgeTextRegistry.setOverride(key, edit.oldValue)
                    if (edit.property.isNotEmpty() && edit.property != key) {
                        BridgeTextRegistry.setOverride(edit.property, edit.oldValue)
                    }
                } else {
                    BridgeThemeRegistry.setColorHex(edit.tokenName, edit.oldValue)
                }
            }
        }
        pendingEdits.clear()
        previewColors.clear()
        syncInProgress = false
    }
}

