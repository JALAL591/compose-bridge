@file:OptIn(
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

package com.composebridge.agent

import androidx.compose.foundation.ExperimentalFoundationApi

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GlobalPanels() {
    var showElementPanel by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(BridgeState.snackbarMessage) {
        BridgeState.snackbarMessage?.let { msg ->
            snackbarHostState.showSnackbar(msg)
            BridgeState.snackbarMessage = null
        }
    }

    // Dialog state for shared colors (Improvement 4)
    var colorPendingChange by remember { mutableStateOf<ElementColorInfo?>(null) }
    var pendingNewHex by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(DesignModeRegistry.selectedSourceFile, DesignModeRegistry.selectedSourceLine) {
        val file = DesignModeRegistry.selectedSourceFile
        val line = DesignModeRegistry.selectedSourceLine
        if (file != null && line > 0) {
            showElementPanel = true
            BridgeState.isLoadingElementColors = true
            BridgeState.elementAnalysisError = null

            // Improvement 3: 3-second timeout for element color loading
            delay(3000)
            if (BridgeState.isLoadingElementColors) {
                BridgeState.isLoadingElementColors = false
                BridgeState.elementAnalysisError = "Failed to load element colors (timeout)"
            }
        } else {
            showElementPanel = false
            BridgeState.clearElementColors()
        }
    }

    if (showElementPanel) {
        val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
        val scrollState = rememberScrollState()

        ModalBottomSheet(
            onDismissRequest = {
                showElementPanel = false
                // ⭐ Clear data
                BridgeState.elementColors.clear()
                BridgeState.elementDimensions.clear()
                BridgeState.elementComposableName = ""
                BridgeState.isLoadingElementColors = false
                DesignModeRegistry.selectedSourceFile = null
                DesignModeRegistry.selectedSourceLine = 0
            },
            sheetState = sheetState,
        ) {
            if (BridgeState.isLoadingElementColors) {
                // ⭐ Skeleton
                SkeletonContent()
            } else {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .imePadding()
                        .verticalScroll(scrollState)
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                ) {
                    // ═══ Agent Status Bar ═══
                    AgentStatusBar()

                    // Header
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "🎯 Focus Mode — ${BridgeState.elementComposableName.ifEmpty { "Element" }}",
                                fontSize = 17.sp,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(Modifier.height(2.dp))
                            Text(
                                text = "${DesignModeRegistry.selectedSourceFile}:${DesignModeRegistry.selectedSourceLine}",
                                fontSize = 12.sp,
                                color = Color.Gray
                            )
                        }
                    }

                    Spacer(Modifier.height(16.dp))

                    // ═══ Focus Mode — Selected element colors only ═══
                    SectionTitle("🎨 Element Colors")

                    if (BridgeState.elementAnalysisError != null) {
                    Surface(
                        color = Color(0xFFFFEBEE),
                        shape = RoundedCornerShape(8.dp),
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 8.dp)
                    ) {
                        Text(
                            text = "⚠️ ${BridgeState.elementAnalysisError}",
                            fontSize = 12.sp,
                            color = Color(0xFFC62828),
                            modifier = Modifier.padding(10.dp)
                        )
                    }
                } else if (BridgeState.elementColors.isEmpty()) {
                    Text(
                        text = "No custom colors found in this element scope",
                        fontSize = 12.sp,
                        color = Color.Gray,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )
                } else {
                    BridgeState.elementColors.forEach { colorInfo ->
                        if (colorInfo.isThemeDependent) {
                            ThemeDependentColorCard(color = colorInfo)
                        } else {
                            FocusColorRow(
                                colorInfo = colorInfo,
                                onTapHeader = {
                                    if (!colorInfo.isToken) {
                                        BridgeState.hardcodedColorPending = colorInfo
                                        BridgeState.hardcodedUsageGlobal = colorInfo.usageGlobal
                                        BridgeState.hardcodedLocations = colorInfo.locations
                                        BridgeState.hardcodedNewHex = null
                                        BridgeState.showHardcodedDialog = true
                                    }
                                },
                                onPickColor = { newHex ->
                                    if (colorInfo.isToken) {
                                        if (colorInfo.isShared) {
                                            // Dialog for shared tokens
                                            colorPendingChange = colorInfo
                                            pendingNewHex = newHex
                                        } else {
                                            val edit = PendingEdit(
                                                type = "global_color",
                                                file = DesignModeRegistry.selectedSourceFile ?: "",
                                                line = colorInfo.lineInElement,
                                                property = colorInfo.property,
                                                oldValue = colorInfo.value,
                                                newValue = newHex,
                                                tokenName = colorInfo.name,
                                                originalToken = colorInfo.name,
                                                originalValue = colorInfo.value,
                                            )
                                            BridgeState.addPendingEdit(edit)
                                            BridgeState.showSnackbar("📝 Added (${BridgeState.pendingCount})")
                                        }
                                    } else {
                                        // ⭐ hardcoded -> convert dialog
                                        BridgeState.hardcodedColorPending = colorInfo
                                        BridgeState.hardcodedUsageGlobal = colorInfo.usageGlobal
                                        BridgeState.hardcodedLocations = colorInfo.locations
                                        BridgeState.hardcodedNewHex = newHex
                                        BridgeState.showHardcodedDialog = true
                                    }
                                }
                            )
                        }
                    }
                }

                Spacer(Modifier.height(20.dp))

                // ═══ Dimensions ═══
                if (BridgeState.elementDimensions.isNotEmpty()) {
                    SectionTitle("📏 Element Dimensions")

                    BridgeState.elementDimensions.forEach { dim ->
                        DimensionRow(
                            dimension = dim,
                            onValueSelected = { newValue ->
                                // ⭐ Local preview
                                val composableName = if (!dim.functionName.isNullOrEmpty()) dim.functionName
                                    else (BridgeState.elementComposableName.takeIf { it.isNotEmpty() && it != "Element" } ?: "Element")
                                val registryKey = dim.registryKey.ifEmpty {
                                    "${composableName}_${dim.property}_${dim.line}"
                                }
                                BridgeDimensionRegistry.setOverride(registryKey, newValue.dp)

                                // ⭐ Add to Queue
                                if (dim.inSharedFunction && dim.functionCallCount > 1) {
                                    // ⭐ Shared function → Dialog
                                    BridgeState.dimensionPending = dim
                                    BridgeState.dimensionNewValue = newValue
                                    BridgeState.showDimensionDialog = true
                                } else if (dim.isShared && dim.usageGlobal > 1) {
                                    BridgeState.dimensionPending = dim
                                    BridgeState.dimensionNewValue = newValue
                                    BridgeState.showDimensionDialog = true
                                } else {
                                    // ⭐ Direct — Split
                                    addDimensionToQueue(dim, newValue, mode = "split")
                                }
                            },
                        )
                    }
                } else {
                    SectionTitle("📏 Element Dimensions")
                    Text(
                        text = "ℹ️ No editable dimensions in this element",
                        fontSize = 12.sp,
                        color = Color.Gray,
                        modifier = Modifier.padding(16.dp),
                    )
                }

                Spacer(Modifier.height(16.dp))

                OutlinedButton(
                    onClick = {
                        BridgeDimensionRegistry.clearAll()
                        BridgeThemeRegistry.clearAll()
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text("♻️ Reset All")
                }

                // ═══ Pending Edits Actions in BottomSheet ═══
                if (BridgeState.pendingCount > 0) {
                    Spacer(Modifier.height(12.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = {
                                val edits = BridgeState.pendingEdits.toList()
                                if (edits.isNotEmpty() && !BridgeState.syncInProgress) {
                                    BridgeState.syncInProgress = true
                                    BridgeState.showSnackbar("⏳ Processing ${edits.size} change(s)...")
                                    ComposeBridgeAgent.sendBatchEdits(edits)
                                }
                            },
                            enabled = !BridgeState.syncInProgress,
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF6366F1))
                        ) {
                            Text(
                                if (BridgeState.syncInProgress) "⏳ Syncing..."
                                else "🔄 Sync (${BridgeState.pendingCount})",
                                fontWeight = FontWeight.Bold
                            )
                        }

                        Button(
                            onClick = {
                                BridgeState.clearPendingEdits()
                                BridgeState.showSnackbar("🗑 Cancelled")
                            },
                            enabled = !BridgeState.syncInProgress,
                            modifier = Modifier.weight(1f),
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFDC2626))
                        ) {
                            Text("🗑 Discard All (${BridgeState.pendingCount})", fontWeight = FontWeight.Bold)
                        }
                    }
                }
                Spacer(Modifier.height(32.dp))
                Spacer(Modifier.navigationBarsPadding())
            }
        }
    }
}

    // ═══ Dialog for Shared Colors and Tokens ═══
    val pendingColor = colorPendingChange
    val newHex = pendingNewHex
    if (pendingColor != null && newHex != null) {
        val isSharedValue = (pendingColor.isShared && pendingColor.usageGlobal > 1) || pendingColor.usageGlobal > 1
        if (isSharedValue) {
            val locations = pendingColor.locations
            AlertDialog(
                onDismissRequest = {
                    colorPendingChange = null
                    pendingNewHex = null
                },
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("🔗", fontSize = 24.sp)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            "Shared Value",
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp,
                        )
                    }
                },
                text = {
                    Column(
                        modifier = Modifier
                            .heightIn(max = 400.dp)
                            .verticalScroll(rememberScrollState()),
                    ) {
                        // ⭐ Value name and count
                        Text(
                            text = "Color '${pendingColor.name}' (${pendingColor.value})",
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = "Used in ${pendingColor.usageGlobal} occurrences in project",
                            color = Color(0xFFE65100),
                            fontWeight = FontWeight.Bold,
                        )

                        Spacer(Modifier.height(12.dp))
                        Divider()
                        Spacer(Modifier.height(12.dp))

                        // ⭐ Locations list
                        Text(
                            text = "📍 Locations:",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                        )
                        Spacer(Modifier.height(8.dp))

                        if (locations.isNotEmpty()) {
                            locations.take(10).forEach { loc ->
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(vertical = 4.dp, horizontal = 8.dp),
                                ) {
                                    Text("•", color = Color(0xFF6366F1))
                                    Spacer(Modifier.width(6.dp))
                                    Column {
                                        Text(
                                            text = "${loc.file}:${loc.line}",
                                            fontSize = 12.sp,
                                            fontFamily = FontFamily.Monospace,
                                            color = Color(0xFF6366F1),
                                        )
                                        if (loc.property.isNotEmpty()) {
                                            Text(
                                                text = "  property: ${loc.property}",
                                                fontSize = 11.sp,
                                                color = Color.Gray,
                                            )
                                        }
                                    }
                                }
                            }

                            if (locations.size > 10) {
                                Text(
                                    text = "... and ${locations.size - 10} more locations",
                                    fontSize = 12.sp,
                                    color = Color.Gray,
                                    modifier = Modifier.padding(start = 20.dp, top = 4.dp),
                                )
                            }
                        } else {
                            Text(
                                text = "Appears across multiple files in the project",
                                fontSize = 12.sp,
                                color = Color.Gray,
                                modifier = Modifier.padding(start = 8.dp),
                            )
                        }

                        Spacer(Modifier.height(16.dp))
                        Divider()
                        Spacer(Modifier.height(12.dp))

                        // ⭐ Explain both options
                        Text(
                            text = "🔀 Split for This Element (Recommended):",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp,
                            color = Color(0xFF10B981),
                        )
                        Text(
                            text = "Creates a new dedicated token for this element only.\nOther occurrences retain the original color.",
                            fontSize = 11.sp,
                            color = Color.Gray,
                        )

                        Spacer(Modifier.height(12.dp))

                        Text(
                            text = "🌍 Edit Globally:",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp,
                            color = Color(0xFFE65100),
                        )
                        Text(
                            text = "Updates all ${pendingColor.usageGlobal} occurrences.\n⚠️ Affects the entire application!",
                            fontSize = 11.sp,
                            color = Color.Gray,
                        )
                    }
                },
                confirmButton = {
                    Button(
                        onClick = {
                            if (BridgeState.syncInProgress) return@Button
                            val newTokenName = suggestLocalTokenName(BridgeState.elementComposableName, newHex, pendingColor)
                            val edit = PendingEdit(
                                type = "split_token",
                                file = DesignModeRegistry.selectedSourceFile ?: "",
                                line = pendingColor.lineInElement,
                                property = pendingColor.property,
                                oldValue = pendingColor.value,
                                newValue = newHex,
                                tokenName = newTokenName,
                                originalToken = if (pendingColor.isToken) pendingColor.name else pendingColor.value,
                                occurrences = pendingColor.occurrencesInElement,
                            )
                            BridgeState.addPendingEdit(edit)
                            BridgeState.showSnackbar("✂️ Split token ($newTokenName)")
                            colorPendingChange = null
                            pendingNewHex = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF10B981),
                        )
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text("🔀 Split for This Element", fontWeight = FontWeight.Bold, fontSize = 14.sp)
                            Text("Safe — does not affect others", fontSize = 10.sp)
                        }
                    }
                },
                dismissButton = {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedButton(
                            onClick = {
                                if (BridgeState.syncInProgress) return@OutlinedButton
                                val tokenName = if (pendingColor.isToken && isValidKotlinIdentifier(pendingColor.name)) {
                                    pendingColor.name
                                } else {
                                    suggestGlobalTokenName(pendingColor, newHex)
                                }
                                val edit = PendingEdit(
                                    type = "global_color",
                                    file = DesignModeRegistry.selectedSourceFile ?: "",
                                    line = pendingColor.lineInElement,
                                    property = "all",
                                    oldValue = pendingColor.value,
                                    newValue = newHex,
                                    tokenName = tokenName,
                                )
                                BridgeState.addPendingEdit(edit)
                                BridgeState.showSnackbar("🌍 Global edit added (${pendingColor.usageGlobal} occurrences)")
                                colorPendingChange = null
                                pendingNewHex = null
                            },
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = Color(0xFFE65100),
                            )
                        ) {
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                Text("🌍 Edit Globally", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                                Text("⚠️ ${pendingColor.usageGlobal} places", fontSize = 10.sp)
                            }
                        }
                        TextButton(
                            onClick = {
                                colorPendingChange = null
                                pendingNewHex = null
                            }
                        ) {
                            Text("Cancel", fontSize = 12.sp)
                        }
                    }
                }
            )
        } else if (pendingColor.isToken) {
            AlertDialog(
                onDismissRequest = {
                    colorPendingChange = null
                    pendingNewHex = null
                },
                title = {
                    Text(
                        text = "🔗 Edit Token",
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp
                    )
                },
                text = {
                    Text(
                        text = "Color '${pendingColor.name}' (${pendingColor.value}) exists as a token.\n\nUpdating its value will affect this element.",
                        fontSize = 14.sp
                    )
                },
                confirmButton = {
                    Button(
                        onClick = {
                            val edit = PendingEdit(
                                type = "global_color",
                                file = DesignModeRegistry.selectedSourceFile ?: "",
                                line = pendingColor.lineInElement,
                                property = "all",
                                oldValue = pendingColor.value,
                                newValue = newHex,
                                tokenName = pendingColor.name,
                            )
                            BridgeState.addPendingEdit(edit)
                            BridgeState.showSnackbar("📝 Added (${BridgeState.pendingCount})")
                            colorPendingChange = null
                            pendingNewHex = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF6366F1)
                        )
                    ) {
                        Text("Update Value", fontWeight = FontWeight.Bold)
                    }
                },
                dismissButton = {
                    TextButton(
                        onClick = {
                            colorPendingChange = null
                            pendingNewHex = null
                        }
                    ) {
                        Text("Cancel")
                    }
                }
            )
        }
    }

    // ═══ Dialog: Convert Hardcoded to Token ═══
    val hardcodedColor = BridgeState.hardcodedColorPending
    if (BridgeState.showHardcodedDialog && hardcodedColor != null && !hardcodedColor.isThemeDependent) {
        AlertDialog(
            onDismissRequest = {
                BridgeState.showHardcodedDialog = false
                BridgeState.hardcodedColorPending = null
                BridgeState.hardcodedNewHex = null
            },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("🎨", fontSize = 24.sp)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Hardcoded Color",
                        fontWeight = FontWeight.Bold,
                        fontSize = 17.sp,
                    )
                }
            },
            text = {
                Column(
                    modifier = Modifier
                        .heightIn(max = 400.dp)
                        .verticalScroll(rememberScrollState()),
                ) {
                    // ⭐ Color display
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(
                            modifier = Modifier
                                .size(32.dp)
                                .background(
                                    hexToColor(hardcodedColor.value),
                                    CircleShape,
                                )
                        )
                        Spacer(Modifier.width(12.dp))
                        Column {
                            Text(
                                text = hardcodedColor.name,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(
                                text = hardcodedColor.value,
                                fontSize = 12.sp,
                                color = Color.Gray,
                            )
                        }
                    }

                    Spacer(Modifier.height(12.dp))
                    Divider()
                    Spacer(Modifier.height(12.dp))

                    // ⭐ Explanation
                    Text(
                        text = "⚠️ This color is hardcoded directly in source code",
                        fontSize = 13.sp,
                        color = Color(0xFFE65100),
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        text = "To edit it, it must first be converted into a token.",
                        fontSize = 12.sp,
                        color = Color.Gray,
                    )

                    // ⭐ Count of locations
                    if (hardcodedColor.usageGlobal > 1) {
                        Spacer(Modifier.height(12.dp))
                        Text(
                            text = "📍 Used in ${hardcodedColor.usageGlobal} occurrences",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.SemiBold,
                        )

                        // ⭐ Locations list (first 5)
                        hardcodedColor.locations.take(5).forEach { loc ->
                            Row(
                                modifier = Modifier.padding(
                                    start = 16.dp,
                                    top = 2.dp,
                                ),
                            ) {
                                Text("•", color = Color(0xFF6366F1), fontSize = 11.sp)
                                Spacer(Modifier.width(4.dp))
                                Text(
                                    text = "${loc.file.substringAfterLast("/")}:${loc.line}",
                                    fontSize = 11.sp,
                                    fontFamily = FontFamily.Monospace,
                                    color = Color(0xFF6366F1),
                                )
                            }
                        }

                        if (hardcodedColor.locations.size > 5) {
                            Text(
                                text = "... and ${hardcodedColor.locations.size - 5} more locations",
                                fontSize = 11.sp,
                                color = Color.Gray,
                                modifier = Modifier.padding(start = 20.dp, top = 2.dp),
                            )
                        }
                    }

                    Spacer(Modifier.height(12.dp))
                    Divider()
                    Spacer(Modifier.height(12.dp))

                    // ⭐ Options explanation
                    Text(
                        text = "🔀 Convert for This Element (Recommended):",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color(0xFF10B981),
                    )
                    Text(
                        text = "Creates a new token dedicated to this element only.",
                        fontSize = 11.sp,
                        color = Color.Gray,
                    )

                    Spacer(Modifier.height(8.dp))

                    Text(
                        text = "🌍 Convert Globally:",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = Color(0xFFE65100),
                    )
                    Text(
                        text = "Replaces all ${hardcodedColor.usageGlobal} occurrences with a shared token.",
                        fontSize = 11.sp,
                        color = Color.Gray,
                    )

                    Spacer(Modifier.height(12.dp))
                    Divider()
                    Spacer(Modifier.height(8.dp))

                    // ⭐ Rebuild note
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(
                                Color(0xFFFFF3E0),
                                RoundedCornerShape(8.dp),
                            )
                            .padding(8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("⚠️", fontSize = 16.sp)
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = "Initial conversion requires a rebuild to apply. Subsequent edits will be instant.",
                            fontSize = 11.sp,
                            color = Color(0xFFE65100),
                        )
                    }
                }
            },
            confirmButton = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Button(
                        onClick = {
                            // ⭐ Split: for this element only
                            val color = BridgeState.hardcodedColorPending
                            if (color != null) {
                                performConvertHardcoded(
                                    color = color,
                                    mode = "split",  // ⭐ element-only
                                )
                            }
                            BridgeState.showHardcodedDialog = false
                            BridgeState.hardcodedColorPending = null
                            BridgeState.hardcodedNewHex = null
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Color(0xFF10B981),
                        ),
                        shape = RoundedCornerShape(10.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                "🔀 Convert for This Element",
                                fontWeight = FontWeight.Bold,
                                fontSize = 13.sp,
                            )
                            Text(
                                "Safe — does not affect others",
                                fontSize = 10.sp,
                            )
                        }
                    }

                    OutlinedButton(
                        onClick = {
                            val color = BridgeState.hardcodedColorPending
                            if (color != null) {
                                performConvertHardcoded(
                                    color = color,
                                    mode = "global",  // ⭐ all places
                                )
                            }
                            BridgeState.showHardcodedDialog = false
                            BridgeState.hardcodedColorPending = null
                            BridgeState.hardcodedNewHex = null
                        },
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = Color(0xFFE65100),
                        ),
                        shape = RoundedCornerShape(10.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                "🌍 Convert Globally",
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                            )
                            Text(
                                "⚠️ ${hardcodedColor.usageGlobal} places",
                                fontSize = 10.sp,
                            )
                        }
                    }

                    TextButton(
                        onClick = {
                            BridgeState.showHardcodedDialog = false
                            BridgeState.hardcodedColorPending = null
                            BridgeState.hardcodedNewHex = null
                        },
                        contentPadding = PaddingValues(vertical = 2.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Cancel", fontSize = 12.sp, color = Color.Gray)
                    }
                }
            },
            dismissButton = null
        )
    }

    // ═══ Dialog: Shared Dimension (Split/Global Dialog) ═══
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

    // ═══ FAB Sync Button (When Pending Edits Exist) ═══
    if (DesignModeRegistry.isActive && BridgeState.pendingCount > 0) {
        Box(modifier = Modifier.fillMaxSize()) {
            ExtendedFloatingActionButton(
                onClick = {
                    val edits = BridgeState.pendingEdits.toList()
                    if (edits.isNotEmpty() && !BridgeState.syncInProgress) {
                        BridgeState.syncInProgress = true
                        BridgeState.showSnackbar("⏳ Processing ${edits.size} change(s)...")
                        ComposeBridgeAgent.sendBatchEdits(edits)
                    }
                },
                icon = {
                    if (BridgeState.syncInProgress) {
                        CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp
                        )
                    }
                },
                text = {
                    Text(
                        if (BridgeState.syncInProgress) "Syncing..."
                        else "🔄 Sync (${BridgeState.pendingCount})",
                        fontWeight = FontWeight.Bold
                    )
                },
                containerColor = Color(0xFF6366F1),
                contentColor = Color.White,
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .padding(16.dp)
            )
        }
    }

    // ═══ Snackbar Host ═══
    Box(modifier = Modifier.fillMaxSize()) {
        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 80.dp),
        )
    }
}

private fun isValidKotlinIdentifier(name: String): Boolean {
    if (name.isEmpty()) return false
    if (!name[0].isLetter() && name[0] != '_') return false
    return name.all { it.isLetterOrDigit() || it == '_' }
}

private fun hexToColorName(hex: String): String {
    val clean = hex.removePrefix("#").take(6)
    if (clean.length != 6) return "Custom"
    
    val r = clean.substring(0, 2).toIntOrNull(16) ?: return "Custom"
    val g = clean.substring(2, 4).toIntOrNull(16) ?: return "Custom"
    val b = clean.substring(4, 6).toIntOrNull(16) ?: return "Custom"
    
    return when {
        r > 230 && g > 230 && b > 230 -> "White"
        r < 30 && g < 30 && b < 30 -> "Black"
        kotlin.math.abs(r - g) < 20 && kotlin.math.abs(g - b) < 20 -> "Gray"
        g > r && g > b -> "Green"
        b > r && b > g -> "Blue"
        r > 200 && g in 100..180 && b < 100 -> "Orange"
        r > 200 && g > 200 && b < 100 -> "Yellow"
        r > 200 && b > 100 && g < 150 -> "Pink"
        r > 100 && b > 150 && g < r -> "Purple"
        g > 150 && b > 150 && r < 100 -> "Cyan"
        r > 180 && g < 100 && b < 100 -> "Red"
        else -> "Custom"
    }
}

private fun suggestGlobalTokenName(
    color: ElementColorInfo,
    newHex: String,
): String {
    // ⭐ 1. If token exists and valid, use its name
    if (color.isToken && isValidKotlinIdentifier(color.name)) {
        return color.name
    }
    
    // ⭐ 2. Derive name from color.name
    val baseName = when {
        color.name.startsWith("Color(0x") -> ""
        color.name.startsWith("Color.") -> color.name.removePrefix("Color.")
        isValidKotlinIdentifier(color.name) -> color.name
        else -> ""
    }
    
    // ⭐ 3. Compute color name from newHex
    val colorFromHex = hexToColorName(newHex)
    
    // ⭐ 4. Compose name
    val candidate = if (baseName.isNotEmpty()) {
        "Success${baseName}${colorFromHex}"
    } else {
        "Success${colorFromHex}"
    }
    
    // ⭐ 5. Validate name
    return if (isValidKotlinIdentifier(candidate)) {
        candidate
    } else {
        "SuccessCustom${System.currentTimeMillis() % 1000}"
    }
}

private fun suggestLocalTokenName(
    elementName: String,
    newHex: String,
    color: ElementColorInfo,
): String {
    // ⭐ Clean elementName
    val cleanElement = elementName
        .replace(Regex("[^A-Za-z0-9_]"), "")
        .ifEmpty { "Element" }
    
    val colorName = hexToColorName(newHex)
    val candidate = "${cleanElement}${colorName}Accent"
    
    return if (isValidKotlinIdentifier(candidate)) {
        candidate
    } else {
        "Accent${System.currentTimeMillis() % 1000}"
    }
}

private fun propertyLabel(prop: String): String = when (prop.lowercase()) {
    "c1" -> "Primary Color (c1)"
    "c2" -> "Secondary Color (c2)"
    "background" -> "Background Color (background)"
    "color" -> "Color"
    "containercolor" -> "Container Color (containerColor)"
    "contentcolor" -> "Content Color (contentColor)"
    "tint" -> "Icon Tint (tint)"
    "textcolor" -> "Text Color (textColor)"
    "border" -> "Border Color (border)"
    else -> prop
}

@Composable
private fun ThemeDependentColorCard(
    color: ElementColorInfo,
) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .clickable {
                BridgeState.showSnackbar("⚠️ This color follows app theme — cannot be edited directly")
            },
        shape = RoundedCornerShape(8.dp),
        color = Color(0xFFF3F4F6),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🎨", fontSize = 18.sp)
                Spacer(Modifier.width(8.dp))
                Column {
                    Text(
                        text = propertyLabel(color.property),
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                        color = Color(0xFF1E293B),
                    )
                    Text(
                        text = color.name,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace,
                        color = Color.Gray,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("⚠️", fontSize = 14.sp)
                Spacer(Modifier.width(4.dp))
                Text(
                    text = "Follows app theme — updates automatically",
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFE65100),
                )
            }
            Text(
                text = "For independent edits, use Split after converting",
                fontSize = 10.sp,
                color = Color.Gray,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}

@Composable
private fun FocusColorRow(
    colorInfo: ElementColorInfo,
    onTapHeader: (() -> Unit)? = null,
    onPickColor: (String) -> Unit,
) {
    if (colorInfo.isThemeDependent) {
        ThemeDependentColorCard(color = colorInfo)
        return
    }

    val currentEffectiveHex = BridgeState.previewColors[colorInfo.name] ?: colorInfo.value
    var selectedHex by remember(currentEffectiveHex) { mutableStateOf(currentEffectiveHex) }

    val basePalette = listOf(
        "#1E3A8A", // Dark Blue
        "#3B82F6", // Blue
        "#10B981", // Green
        "#F59E0B", // Orange
        "#EF4444", // Red
        "#8B5CF6", // Purple
        "#EC4899", // Pink
        "#14B8A6", // Teal
        "#FFFFFF", // White
        "#1E293B", // Dark Slate
    )

    val palette = remember(colorInfo.value) {
        val clean = colorInfo.value.trim().uppercase()
        if (clean.startsWith("#") && basePalette.none { it.equals(clean, ignoreCase = true) }) {
            listOf(clean) + basePalette
        } else {
            basePalette
        }
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 10.dp)
    ) {
        // ⭐ Title and badge
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .then(
                    if (!colorInfo.isToken) Modifier.clickable { onTapHeader?.invoke() }
                    else Modifier
                ),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = "${propertyLabel(colorInfo.property)}:",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF1E293B)
                )

                if (!colorInfo.isToken) {
                    Text(
                        text = colorInfo.name,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        fontFamily = FontFamily.Monospace,
                        color = Color(0xFF475569)
                    )
                }

                // ⭐ Status badge
                when {
                    colorInfo.isToken && colorInfo.isShared -> {
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = Color(0xFF6366F1).copy(alpha = 0.12f),
                        ) {
                            Text(
                                text = "🔗 Shared Token (${colorInfo.usageGlobal})",
                                fontSize = 10.sp,
                                color = Color(0xFF6366F1),
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                    colorInfo.isToken -> {
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = Color(0xFF10B981).copy(alpha = 0.12f),
                        ) {
                            Text(
                                text = "🔗 Standalone Token",
                                fontSize = 10.sp,
                                color = Color(0xFF10B981),
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                    else -> {
                        // ⭐ hardcoded
                        Surface(
                            shape = RoundedCornerShape(4.dp),
                            color = Color(0xFFE65100).copy(alpha = 0.12f),
                            modifier = Modifier.clickable {
                                onTapHeader?.invoke()
                            }
                        ) {
                            Text(
                                text = "⚠️ Hardcoded — Tap to Convert",
                                fontSize = 10.sp,
                                color = Color(0xFFE65100),
                                fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            )
                        }
                    }
                }
            }

            Text(
                text = selectedHex,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                color = Color(0xFF6366F1)
            )
        }

        Spacer(Modifier.height(8.dp))

        // ⭐ Color bar with highlight and scroll
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            palette.forEach { hex ->
                val isSelected = hex.equals(selectedHex, ignoreCase = true)
                val isWhiteOrLight = hex.equals("#FFFFFF", ignoreCase = true) || hex.equals("#F1F5F9", ignoreCase = true)
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(hexToColor(hex))
                        .border(
                            width = if (isSelected) 3.dp else 1.dp,
                            color = if (isSelected) Color(0xFF6366F1) else Color.Gray.copy(alpha = 0.3f),
                            shape = CircleShape
                        )
                        .clickable {
                            selectedHex = hex
                            onPickColor(hex)
                        },
                    contentAlignment = Alignment.Center
                ) {
                    if (isSelected) {
                        Icon(
                            imageVector = Icons.Default.Check,
                            contentDescription = "Selected",
                            tint = if (isWhiteOrLight) Color(0xFF1E293B) else Color.White,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SkeletonContent() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
    ) {
        repeat(4) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(60.dp)
                    .padding(vertical = 4.dp)
                    .background(
                        Color(0xFFE5E7EB),
                        RoundedCornerShape(8.dp),
                    )
            )
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "⏳ Loading element info...",
            fontSize = 12.sp,
            color = Color.Gray,
        )
    }
}

@Composable
private fun SkeletonColorRow() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .width(130.dp)
                    .height(18.dp)
                    .background(Color(0xFFE2E8F0), RoundedCornerShape(4.dp))
            )
            Box(
                modifier = Modifier
                    .width(60.dp)
                    .height(14.dp)
                    .background(Color(0xFFE2E8F0), RoundedCornerShape(4.dp))
            )
        }
        Spacer(Modifier.height(8.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            repeat(8) {
                Box(
                    modifier = Modifier
                        .size(32.dp)
                        .background(Color(0xFFE2E8F0), CircleShape)
                )
            }
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        fontSize = 15.sp,
        fontWeight = FontWeight.Bold,
        color = Color(0xFF6366F1),
        modifier = Modifier.padding(vertical = 6.dp)
    )
}

private fun addDimensionToQueue(
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
        file = if (dim.file.isNotEmpty()) dim.file else (DesignModeRegistry.selectedSourceFile ?: ""),
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

@Composable
private fun DimensionRow(
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

    // ⭐ Common values
    val commonValues = listOf(4f, 8f, 12f, 16f, 20f, 24f, 32f, 40f, 48f, 64f)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        // ═══ Header ═══
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

            // ⭐ Current value
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = Color(0xFF6366F1).copy(alpha = 0.12f),
            ) {
                Text(
                    text = "${dimension.currentValue.toInt()}.${dimension.kind}",
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = Color(0xFF6366F1),
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                )
            }
        }

        Spacer(Modifier.height(8.dp))

        // ═══ Common Values (Chips) ═══
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            items(commonValues) { value ->
                val isSelected = value == dimension.currentValue

                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = if (isSelected)
                        Color(0xFF6366F1)
                    else
                        Color(0xFFF3F4F6),
                    modifier = Modifier
                        .clickable {
                            onValueSelected(value)
                        }
                        .widthIn(min = 48.dp),
                ) {
                    Text(
                        text = "${value.toInt()}",
                        fontSize = 13.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                        color = if (isSelected) Color.White else Color(0xFF374151),
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        textAlign = TextAlign.Center,
                    )
                }
            }

            // ⭐ Manual input button
            item {
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = Color(0xFFFFF3E0),
                    modifier = Modifier
                        .clickable {
                            showManualInput = !showManualInput
                        }
                        .widthIn(min = 48.dp),
                ) {
                    Text(
                        text = "✏️",
                        fontSize = 14.sp,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }

        // ═══ Manual Input ═══
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
                    onValueChange = { newText ->
                        // ⭐ Numbers only
                        manualInput = newText.filter { it.isDigit() }
                    },
                    label = { Text("Value (${dimension.kind})") },
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Number,
                        imeAction = ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(
                        onDone = {
                            val v = manualInput.toFloatOrNull()
                            if (v != null) {
                                onValueSelected(v)
                                showManualInput = false
                            }
                        }
                    ),
                    singleLine = true,
                    modifier = Modifier
                        .weight(1f)
                        .focusRequester(focusRequester),
                )

                Button(
                    onClick = {
                        val v = manualInput.toFloatOrNull()
                        if (v != null) {
                            onValueSelected(v)
                            showManualInput = false
                        }
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color(0xFF10B981),
                    ),
                ) {
                    Text("Apply", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

private fun dimensionLabel(property: String): String = when (property) {
    "height" -> "Height"
    "width" -> "Width"
    "size" -> "Size"
    "padding" -> "Padding"
    "padding_horizontal" -> "Horizontal Padding"
    "padding_vertical" -> "Vertical Padding"
    "fontSize" -> "Font Size"
    "letterSpacing" -> "Letter Spacing"
    "cornerRadius" -> "Corner Radius"
    "minHeight" -> "Min Height"
    "minWidth" -> "Min Width"
    "borderWidth" -> "Border Width"
    else -> property
}

@Composable
fun AgentStatusBar() {
    val agentBusy = BridgeState.agentBusy
    val queueCount = BridgeState.queueCount
    val isConnected = BridgeState.isConnected
    val isReconnecting = BridgeState.isReconnecting

    LaunchedEffect(Unit) {
        ComposeBridgeAgent.requestQueueStatus()
    }

    val statusBg = when {
        isReconnecting -> Color(0xFFFFF8E1)
        !isConnected -> Color(0xFFFFEBEE)
        agentBusy -> Color(0xFFFFF3E0)
        else -> Color(0xFFE8F5E9)
    }

    val statusText = when {
        isReconnecting -> "🔄 Reconnecting..."
        !isConnected -> "🔴 Disconnected"
        agentBusy -> "🤖 Agent busy..."
        else -> "🟢 Bridge Running"
    }

    val statusColor = when {
        isReconnecting -> Color(0xFFF59E0B)
        !isConnected -> Color(0xFFEF4444)
        agentBusy -> Color(0xFFE65100)
        else -> Color(0xFF2E7D32)
    }

    Surface(
        color = statusBg,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = statusText,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = statusColor
                )
                if (queueCount > 0) {
                    Text(
                        text = "📥 $queueCount pending edit(s)",
                        fontSize = 12.sp,
                        color = Color(0xFF616161)
                    )
                }
            }

            if (queueCount > 0) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = {
                            ComposeBridgeAgent.requestQueueClear()
                        },
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                    ) {
                        Text("🗑️", fontSize = 12.sp)
                    }
                    val syncing = BridgeState.syncing
                    Button(
                        onClick = {
                            BridgeState.setSyncing(true)
                            ComposeBridgeAgent.requestUserSync()
                        },
                        enabled = !syncing,
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                    ) {
                        if (syncing) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(12.dp),
                                    strokeWidth = 2.dp,
                                    color = Color.White
                                )
                                Text("Syncing...", fontSize = 12.sp)
                            }
                        } else {
                            Text("🔄 Sync", fontSize = 12.sp)
                        }
                    }
                }
            }
        }
    }

    Spacer(Modifier.height(12.dp))
}

private fun parseHexColor(hex: String): Color = hexToColor(hex)

private fun hexToColor(hex: String): Color {
    return try {
        val cleaned = hex.removePrefix("#").removePrefix("0x").removePrefix("0X")
        val argb = if (cleaned.length == 6) "FF$cleaned" else cleaned
        Color(argb.toLong(16))
    } catch (e: Exception) {
        Color.Gray
    }
}

private fun performConvertHardcoded(
    color: ElementColorInfo,
    mode: String,  // "split" | "global"
) {
    if (BridgeState.syncInProgress) {
        BridgeState.showSnackbar("⏳ Sync in progress...")
        return
    }

    // ⭐ 1. Compute token name
    val elementName = BridgeState.elementComposableName
    val targetHex = BridgeState.hardcodedNewHex ?: color.value
    val suggestedName = if (mode == "split") {
        // ⭐ Dedicated to this element
        suggestLocalTokenName(elementName, targetHex, color)
    } else {
        // ⭐ Shared — generic name
        suggestGlobalTokenName(color, targetHex)
    }

    android.util.Log.i("ComposeBridge", "🎨 performConvertHardcoded:")
    android.util.Log.i("ComposeBridge", "   mode=$mode")
    android.util.Log.i("ComposeBridge", "   color=${color.name} ${color.value}")
    android.util.Log.i("ComposeBridge", "   suggestedName=$suggestedName")

    // ⭐ 2. Build occurrences JSON
    val occsJson = color.occurrencesInElement.joinToString(",", "[", "]") {
        """{"line":${it.line},"property":"${it.property}"}"""
    }

    // ⭐ 3. PendingEdit
    val edit = PendingEdit(
        id = java.util.UUID.randomUUID().toString(),
        type = if (mode == "split") "split_token" else "global_color",
        file = DesignModeRegistry.selectedSourceFile ?: "",
        line = color.lineInElement,
        property = color.property,
        oldValue = color.value,
        newValue = targetHex,  // ⭐ Value for conversion
        tokenName = suggestedName,
        timestamp = System.currentTimeMillis(),
        occurrencesJson = if (mode == "split") occsJson else null,
        occurrences = if (mode == "split") color.occurrencesInElement else emptyList(),
        originalToken = color.name,
        originalValue = color.value,
    )

    BridgeState.addPendingEdit(edit)
    BridgeState.hardcodedNewHex = null

    val modeText = if (mode == "split") "for this element" else "globally"
    BridgeState.showSnackbar(
        "📝 Added ($modeText) — ${BridgeState.pendingCount}\n⚠️ Rebuild required first time"
    )

    android.util.Log.i("ComposeBridge", "✅ Convert hardcoded added to queue")
}
