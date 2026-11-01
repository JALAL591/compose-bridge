/**
 * ComposeBridge Text Edit Panel.
 * لوحة فحص وتعديل النصوص والسلاسل النصية لعناصر الواجهة.
 */
package com.composebridge.agent.ui.panels

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.composebridge.agent.BridgeState
import com.composebridge.agent.BridgeTextRegistry
import com.composebridge.agent.PendingEdit

/**
 * لوحة تعديل النصوص المعروضة في العنصر المحدد ومزامنتها لحظياً.
 * Composable panel for inspecting and modifying text elements in the current element scope.
 */
@Composable
fun TextEditPanel() {
    Text(
        text = "📝 Element Text",
        fontSize = 14.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(vertical = 4.dp)
    )

    if (BridgeState.elementTexts.isEmpty()) {
        Text(
            text = "ℹ️ No editable text string detected in current element scope",
            fontSize = 12.sp,
            color = Color.Gray,
            modifier = Modifier.padding(12.dp),
        )
    } else {
        BridgeState.elementTexts.forEachIndexed { idx, textInfo ->
            var localText by remember(textInfo.text) { mutableStateOf(textInfo.text) }
            var applied by remember(textInfo.text) { mutableStateOf(false) }

            LaunchedEffect(textInfo.text) {
                localText = textInfo.text
                applied = false
            }

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 4.dp),
                shape = RoundedCornerShape(12.dp),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f)
                )
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    if (textInfo.isResourceOrRef && !textInfo.refKey.isNullOrEmpty()) {
                        Text(
                            text = "🔗 Reference: ${textInfo.refKey}",
                            fontSize = 11.sp,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.SemiBold
                        )
                        Spacer(Modifier.height(4.dp))
                    }

                    OutlinedTextField(
                        value = localText,
                        onValueChange = {
                            localText = it
                            applied = false
                        },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Text Content") },
                        singleLine = false,
                        maxLines = 4
                    )

                    Spacer(Modifier.height(8.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.End
                    ) {
                        Button(
                            onClick = {
                                applied = true
                                val editId = java.util.UUID.randomUUID().toString()
                                val refKeyToUse = if (!textInfo.refKey.isNullOrEmpty()) textInfo.refKey
                                                  else if (textInfo.property.startsWith("AppStrings.")) textInfo.property
                                                  else null
                                val targetKey = refKeyToUse ?: textInfo.property.ifEmpty { "text" }
                                BridgeTextRegistry.setOverride(targetKey, localText)
                                if (!textInfo.refKey.isNullOrEmpty() && textInfo.refKey != targetKey) {
                                    BridgeTextRegistry.setOverride(textInfo.refKey, localText)
                                }
                                if (!textInfo.property.isNullOrEmpty() && textInfo.property != targetKey) {
                                    BridgeTextRegistry.setOverride(textInfo.property, localText)
                                }
                                val edit = PendingEdit(
                                    id = editId,
                                    type = "text_edit",
                                    file = textInfo.file,
                                    line = textInfo.line,
                                    property = refKeyToUse ?: textInfo.property.ifEmpty { "text" },
                                    oldValue = textInfo.text,
                                    newValue = localText,
                                    tokenName = refKeyToUse ?: textInfo.property.ifEmpty { "text" },
                                    refKey = refKeyToUse
                                )
                                BridgeState.addPendingEdit(edit)
                                BridgeState.showSnackbar("📝 Added (${BridgeState.pendingCount})")
                            },
                            enabled = localText != textInfo.text && !applied
                        ) {
                            Text(if (applied) "Applied ✓" else "Apply Text")
                        }
                    }
                }
            }
        }
    }
}

