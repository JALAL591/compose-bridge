/**
 * ComposeBridge External Warning Dialog.
 * نافذة التحذير عند اكتشاف تعديلات خارجية على الملفات في الـ IDE أو من مصادر أخرى.
 */
package com.composebridge.agent.ui.panels

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.composebridge.agent.BridgeState
import com.composebridge.agent.ComposeBridgeAgent

@Composable
fun ExternalWarningDialog() {
    val activeWarning = BridgeState.activeWarningDialog ?: return
    AlertDialog(
        onDismissRequest = { BridgeState.activeWarningDialog = null },
        title = {
            Text("⚠️ Warning: External Modifications Detected", fontWeight = FontWeight.Bold)
        },
        text = {
            val fileName = activeWarning.file.substringAfterLast('/').substringAfterLast('\\')
            val displayMessage = if (activeWarning.message.contains("تحذير") || activeWarning.message.contains("تعديله")) {
                "⚠️ Warning: File '$fileName' was modified externally (manually or by another agent). Restoring the backup will overwrite these changes. Are you sure?"
            } else if (activeWarning.message.isNotBlank()) {
                activeWarning.message
            } else {
                "⚠️ Warning: File '$fileName' was modified externally (manually or by another agent). Restoring the backup will overwrite these changes. Are you sure?"
            }
            Text(displayMessage)
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val targetFile = activeWarning.file
                    BridgeState.activeWarningDialog = null
                    ComposeBridgeAgent.transport?.send("{\"type\": \"reject_file_force\", \"file\": \"$targetFile\"}")
                }
            ) {
                Text("Revert Anyway", color = Color(0xFFDC2626), fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            Row {
                TextButton(
                    onClick = {
                        val targetFile = activeWarning.file
                        BridgeState.activeWarningDialog = null
                        ComposeBridgeAgent.transport?.send("{\"type\": \"approve_file\", \"file\": \"$targetFile\"}")
                    }
                ) {
                    Text("Keep Current Edits")
                }
                Spacer(Modifier.width(4.dp))
                TextButton(
                    onClick = {
                        BridgeState.activeWarningDialog = null
                        BridgeState.showSnackbar("📄 Diff check: ${activeWarning.file}")
                    }
                ) {
                    Text("View Diff")
                }
            }
        }
    )
}

