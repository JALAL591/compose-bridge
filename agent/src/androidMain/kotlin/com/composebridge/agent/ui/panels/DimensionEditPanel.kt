@file:OptIn(
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

/**
 * ComposeBridge Dimension Edit Panel.
 * لوحة فحص وتعديل أبعاد ومقاسات عناصر واجهة المستخدم (dp/sp, padding, size).
 */
package com.composebridge.agent.ui.panels

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.composebridge.agent.BridgeDimensionRegistry
import com.composebridge.agent.BridgeState
import com.composebridge.agent.DesignModeRegistry
import com.composebridge.agent.ElementDimensionInfo
import com.composebridge.agent.PendingEdit
import kotlinx.coroutines.delay

/**
 * لوحة عرض وتعديل أبعاد العنصر المختار.
 * Main Dimension Edit Panel displaying editable dimensions of the selected element.
 */
@Composable
fun DimensionEditPanel() {
    Text(
        text = "📐 Element Dimensions",
        fontSize = 14.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(vertical = 4.dp)
    )

    if (BridgeState.elementDimensions.isEmpty()) {
        Text(
            text = "🔍 No editable dimensions detected in current element scope",
            fontSize = 12.sp,
            color = Color.Gray,
            modifier = Modifier.padding(12.dp),
        )
    } else {
        BridgeState.elementDimensions.forEach { dim ->
            DimensionRow(
                dimension = dim,
                onValueSelected = { newVal ->
                    if (dim.isShared) {
                        val composableName = if (!dim.functionName.isNullOrEmpty()) dim.functionName 
                            else (BridgeState.elementComposableName.takeIf { it.isNotEmpty() && it != "Element" } ?: "Element")
                        val rKey = dim.registryKey.ifEmpty { "${composableName}_${dim.property}_${dim.line}" }
                        BridgeDimensionRegistry.setOverride(rKey, newVal.dp)
                        BridgeState.dimensionPending = dim
                        BridgeState.dimensionNewValue = newVal
                        BridgeState.showDimensionDialog = true
                    } else {
                        addDimensionToQueue(dim, newVal, mode = "split")
                    }
                }
            )
        }
    }

    DimensionSharedDialog()
}

/**
 * نافذة حوار للتعامل مع الأبعاد المشتركة بين عدة عناصر أو دوال.
 * Dialog for resolving modifications to shared dimensions across functions or occurrences.
 */
@Composable
fun DimensionSharedDialog() {
    if (BridgeState.showDimensionDialog && BridgeState.dimensionPending != null) {
        val dim = BridgeState.dimensionPending!!
        val newVal = BridgeState.dimensionNewValue ?: dim.currentValue

        if (dim.inSharedFunction && dim.functionCallCount > 1) {
            AlertDialog(
                onDismissRequest = {
                    val composableName = if (!dim.functionName.isNullOrEmpty()) dim.functionName
                        else (BridgeState.elementComposableName.takeIf { it.isNotEmpty() && it != "Element" } ?: "Element")
                    val rKey = dim.registryKey.ifEmpty {
                        "${composableName}_${dim.property}_${dim.line}"
                    }
                    BridgeDimensionRegistry.setOverride(rKey, dim.currentValue.dp)
                    BridgeState.showDimensionDialog = false
                    BridgeState.dimensionPending = null
                    BridgeState.dimensionNewValue = null
                },
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("⚠️", fontSize = 24.sp)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            "Shared Dimension in Function",
                            fontWeight = FontWeight.Bold,
                            fontSize = 17.sp,
                        )
                    }
                },
                text = {
                    Column(
                        modifier = Modifier.heightIn(max = 400.dp).verticalScroll(rememberScrollState()),
                    ) {
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFFFFF3E0),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text(
                                    "📐 ${dim.property}: ${dim.value}",
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp,
                                )
                                Spacer(Modifier.height(6.dp))
                                Text(
                                    "📍 Inside function:",
                                    fontSize = 12.sp,
                                    color = Color.Gray,
                                )
                                Text(
                                    "${dim.functionName}(...)",
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 13.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF6366F1),
                                )
                            }
                        }

                        Spacer(Modifier.height(12.dp))

                        Text(
                            "⚠️ This function is used across ${dim.functionCallCount} callers.",
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp,
                            color = Color(0xFFE65100),
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            "Editing this dimension will affect all ${dim.functionCallCount} callers.",
                            fontSize = 12.sp,
                            color = Color.Gray,
                        )

                        Spacer(Modifier.height(12.dp))
                        HorizontalDivider()
                        Spacer(Modifier.height(12.dp))

                        Text(
                            "New Value: ${newVal.toInt()}.${dim.kind}",
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                            color = Color(0xFF6366F1),
                        )
                    }
                },
                confirmButton = {
                    Column(
                        modifier = Modifier.fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = {
                                addDimensionToQueue(dim, newVal, mode = "split")
                                BridgeState.showDimensionDialog = false
                                BridgeState.dimensionPending = null
                                BridgeState.dimensionNewValue = null
                            },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Color(0xFF10B981),
                            ),
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    "🔀 For This Element (Recommended)",
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 13.sp,
                                )
                                Text(
                                    "Safe — modifies this element only",
                                    fontSize = 10.sp,
                                )
                            }
                        }

                        OutlinedButton(
                            onClick = {
                                addDimensionToQueue(dim, newVal, mode = "global")
                                BridgeState.showDimensionDialog = false
                                BridgeState.dimensionPending = null
                                BridgeState.dimensionNewValue = null
                            },
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = Color(0xFFE65100),
                            ),
                            shape = RoundedCornerShape(10.dp),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(
                                    "🌍 Edit All (${dim.functionCallCount} callers)",
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 12.sp,
                                )
                                Text(
                                    "⚠️ Affects all instances",
                                    fontSize = 10.sp,
                                )
                            }
                        }

                        TextButton(
                            onClick = {
                                val composableName = if (!dim.functionName.isNullOrEmpty()) dim.functionName
                                    else (BridgeState.elementComposableName.takeIf { it.isNotEmpty() && it != "Element" } ?: "Element")
                                val rKey = dim.registryKey.ifEmpty {
                                    "${composableName}_${dim.property}_${dim.line}"
                                }
                                BridgeDimensionRegistry.setOverride(rKey, dim.currentValue.dp)
                                BridgeState.showDimensionDialog = false
                                BridgeState.dimensionPending = null
                                BridgeState.dimensionNewValue = null
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("Cancel", fontSize = 12.sp, color = Color.Gray)
                        }
                    }
                },
                dismissButton = null,
            )
        } else {
            AlertDialog(
                onDismissRequest = {
                    val composableName = if (!dim.functionName.isNullOrEmpty()) dim.functionName
                        else (BridgeState.elementComposableName.takeIf { it.isNotEmpty() && it != "Element" } ?: "Element")
                    val rKey = dim.registryKey.ifEmpty {
                        "${composableName}_${dim.property}_${dim.line}"
                    }
                    BridgeDimensionRegistry.setOverride(rKey, dim.currentValue.dp)
                    BridgeState.showDimensionDialog = false
                    BridgeState.dimensionPending = null
                    BridgeState.dimensionNewValue = null
                },
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("📐", fontSize = 24.sp)
                        Spacer(Modifier.width(8.dp))
                        Text("Shared Value", fontWeight = FontWeight.Bold)
                    }
                },
                text = {
                    Column(
                        modifier = Modifier.heightIn(max = 400.dp).verticalScroll(rememberScrollState()),
                    ) {
                        Text(
                            "Value: ${dim.value}",
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            "Used in ${dim.usageGlobal} occurrences",
                            color = Color(0xFFE65100),
                            fontWeight = FontWeight.Bold,
                        )
                        Spacer(Modifier.height(8.dp))

                        if (dim.locations.isNotEmpty()) {
                            Text("📍 Locations:", fontWeight = FontWeight.SemiBold)
                            dim.locations.take(5).forEach { loc ->
                                Text(
                                    "• ${loc.file}:${loc.line}",
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = Color(0xFF6366F1),
                                )
                            }
                        }

                        Spacer(Modifier.height(12.dp))
                        Text("New Value: ${newVal.toInt()}.${dim.kind}", fontWeight = FontWeight.Bold)
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            addDimensionToQueue(dim, newVal, mode = "split")
                            BridgeState.showDimensionDialog = false
                            BridgeState.dimensionPending = null
                            BridgeState.dimensionNewValue = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF10B981),
                        ),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("🔀 For This Element", fontWeight = FontWeight.Bold)
                            Text("Safe — does not affect others", fontSize = 10.sp)
                        }
                    }
                },
                dismissButton = {
                    Column(modifier = Modifier.fillMaxWidth()) {
                        OutlinedButton(
                            onClick = {
                                addDimensionToQueue(dim, newVal, mode = "global")
                                BridgeState.showDimensionDialog = false
                                BridgeState.dimensionPending = null
                                BridgeState.dimensionNewValue = null
                            },
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = Color(0xFFE65100),
                            ),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("🌍 Edit All", fontWeight = FontWeight.Bold)
                                Text("⚠️ ${dim.usageGlobal} places", fontSize = 10.sp)
                            }
                        }
                        TextButton(
                            onClick = {
                                val composableName = if (!dim.functionName.isNullOrEmpty()) dim.functionName
                                    else (BridgeState.elementComposableName.takeIf { it.isNotEmpty() && it != "Element" } ?: "Element")
                                val rKey = dim.registryKey.ifEmpty {
                                    "${composableName}_${dim.property}_${dim.line}"
                                }
                                BridgeDimensionRegistry.setOverride(rKey, dim.currentValue.dp)
                                BridgeState.showDimensionDialog = false
                                BridgeState.dimensionPending = null
                                BridgeState.dimensionNewValue = null
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("Cancel") }
                    }
                },
            )
        }
    }
}

/**
 * إضافة تعديل بُعد جديد إلى قائمة التعديلات المعلقة.
 * Adds a new dimension modification to pending edits queue.
 */
fun addDimensionToQueue(
    dim: ElementDimensionInfo,
    newValue: Float,
    mode: String,
) {
    val roundedNewVal = newValue.toInt().toFloat()
    val roundedOldVal = dim.currentValue.toInt().toFloat()
    val composableName = if (!dim.functionName.isNullOrEmpty()) dim.functionName 
        else (BridgeState.elementComposableName.takeIf { it.isNotEmpty() && it != "Element" } ?: "Element")
    val registryKey = if (mode == "global") "global_${dim.property}_${roundedOldVal.toInt()}"
        else dim.registryKey.ifEmpty { "${composableName}_${dim.property}_${dim.line}" }
    if (mode == "global") {
        BridgeDimensionRegistry.setOverride(registryKey, roundedNewVal.dp)
    }
    val edit = PendingEdit(
        id = java.util.UUID.randomUUID().toString(),
        type = "dimension",
        file = if (dim.file.isNotEmpty() && !dim.file.endsWith("Text.kt")) dim.file else (DesignModeRegistry.selectedSourceFile ?: ""),
        line = dim.line,
        property = dim.property,
        oldValue = if (dim.currentValue == roundedOldVal) roundedOldVal.toInt().toString() else dim.currentValue.toString(),
        newValue = roundedNewVal.toInt().toString(),
        tokenName = "",
        timestamp = System.currentTimeMillis(),
        dimensionToken = registryKey,
        dimensionValue = roundedNewVal,
        dimensionKind = dim.kind,
        isShared = dim.isShared,
        editMode = mode,
        isTernary = dim.isTernary,
        desktopValue = dim.desktopValue,
        registryKey = registryKey,
    )
    BridgeState.addPendingEdit(edit)
    if (mode == "global") {
        BridgeState.showSnackbar("🌍 Global: Live Preview for all places (${BridgeState.pendingCount})")
    } else {
        BridgeState.showSnackbar("📝 Split: Instant preview (${BridgeState.pendingCount})")
    }
}

/**
 * صف عرض خيارات التعديل السريع للبُعد.
 * Composable row for displaying and selecting dimension values.
 */
@Composable
fun DimensionRow(
    dimension: ElementDimensionInfo,
    onValueSelected: (Float) -> Unit,
) {
    var manualInput by remember(dimension.line, dimension.property) {
        mutableStateOf(dimension.currentValue.toInt().toString())
    }
    var showManualInput by remember { mutableStateOf(false) }
    val focusRequester = remember { FocusRequester() }
    val bringIntoViewRequester = remember { BringIntoViewRequester() }

    LaunchedEffect(showManualInput) {
        if (showManualInput) {
            delay(150)
            try {
                bringIntoViewRequester.bringIntoView()
            } catch (_: Exception) {}
            try {
                focusRequester.requestFocus()
            } catch (_: Exception) {}
        }
    }

    val commonValues = listOf(4f, 8f, 12f, 16f, 20f, 24f, 32f, 40f, 48f, 64f)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = dimensionLabel(dimension.property),
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 14.sp,
                )
                if (dimension.inSharedFunction && dimension.functionCallCount > 1) {
                    Text(
                        text = "⚠️ Function ${dimension.functionName} (${dimension.functionCallCount} callers)",
                        fontSize = 10.sp,
                        color = Color(0xFFE65100),
                    )
                } else {
                    Text(
                        text = "line ${dimension.line}",
                        fontSize = 10.sp,
                        color = Color.Gray,
                    )
                }
            }

            Text(
                text = "${dimension.currentValue.toInt()} ${dimension.kind}",
                fontWeight = FontWeight.Bold,
                fontSize = 14.sp,
                color = Color(0xFF6366F1),
                modifier = Modifier
                    .clickable { showManualInput = !showManualInput }
                    .padding(4.dp),
            )
        }

        Spacer(Modifier.height(8.dp))

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            commonValues.forEach { v ->
                val isSelected = v == dimension.currentValue
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = if (isSelected) Color(0xFF6366F1) else Color.Transparent,
                    border = if (isSelected) null else androidx.compose.foundation.BorderStroke(1.dp, Color(0xFFE0E0E0)),
                    modifier = Modifier.clickable {
                        onValueSelected(v)
                        manualInput = v.toInt().toString()
                        showManualInput = false
                    },
                ) {
                    Text(
                        text = "${v.toInt()}",
                        fontSize = 12.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) Color.White else Color(0xFF424242),
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                    )
                }
            }

            Surface(
                shape = RoundedCornerShape(8.dp),
                color = if (showManualInput) Color(0xFFF3E8FF) else Color.Transparent,
                border = androidx.compose.foundation.BorderStroke(
                    1.dp,
                    if (showManualInput) Color(0xFF9333EA) else Color(0xFFE0E0E0),
                ),
                modifier = Modifier.clickable { showManualInput = !showManualInput },
            ) {
                Text(
                    text = "✏️",
                    fontSize = 12.sp,
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                )
            }
        }

        if (showManualInput) {
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .bringIntoViewRequester(bringIntoViewRequester),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = manualInput,
                    onValueChange = { manualInput = it.filter { c -> c.isDigit() } },
                    label = { Text("Value (${dimension.kind})") },
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Number,
                        imeAction = ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(
                        onDone = {
                            val v = manualInput.toFloatOrNull()
                            if (v != null && v > 0) {
                                onValueSelected(v)
                                showManualInput = false
                            }
                        },
                    ),
                    singleLine = true,
                    modifier = Modifier
                        .weight(1f)
                        .focusRequester(focusRequester),
                )

                Button(
                    onClick = {
                        val v = manualInput.toFloatOrNull()
                        if (v != null && v > 0) {
                            onValueSelected(v)
                            showManualInput = false
                        }
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFF6366F1),
                    ),
                ) {
                    Text("Set")
                }
            }
        }

        Spacer(Modifier.height(8.dp))
        HorizontalDivider(color = Color(0xFFF5F5F5))
    }
}

/**
 * تحويل اسم الخاصية إلى تسمية نصية سهلة القراءة للمستخدم.
 * Returns a human-readable label for a dimension property name.
 */
fun dimensionLabel(property: String): String = when (property) {
    "size" -> "Size"
    "width" -> "Width"
    "height" -> "Height"
    "padding" -> "Padding"
    "paddingValues" -> "Padding Values"
    "horizontalPadding" -> "Horizontal Padding"
    "verticalPadding" -> "Vertical Padding"
    "topPadding" -> "Top Padding"
    "bottomPadding" -> "Bottom Padding"
    "startPadding" -> "Start Padding"
    "endPadding" -> "End Padding"
    "spacing" -> "Arrangement Spacing"
    "corner" -> "Corner Radius"
    "elevation" -> "Elevation"
    "border" -> "Border Width"
    "stroke" -> "Stroke Width"
    "fontSize" -> "Font Size"
    "lineHeight" -> "Line Height"
    else -> property
}
