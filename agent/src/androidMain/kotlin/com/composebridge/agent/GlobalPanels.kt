@file:OptIn(
    androidx.compose.foundation.ExperimentalFoundationApi::class,
    androidx.compose.material3.ExperimentalMaterial3Api::class,
)

package com.composebridge.agent

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.composebridge.agent.ui.panels.AgentStatusBar
import com.composebridge.agent.ui.panels.ColorEditPanel
import com.composebridge.agent.ui.panels.DimensionEditPanel
import com.composebridge.agent.ui.panels.TextEditPanel
import com.composebridge.agent.ui.panels.ExternalWarningDialog
import kotlinx.coroutines.delay

/**
 * ComposeBridge Global Panels (Coordinator & Router).
 * المنسق والموجه الرئيسي لجميع لوحات التعديل والمحاورات في موديول الـ Agent.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GlobalPanels() {
    // ═══ Remote Connection Dialog ═══
    if (BridgeState.showRemoteDialog) {
        RemoteConnectionDialog(
            onDismissRequest = { BridgeState.showRemoteDialog = false }
        )
    }

    // ═══ Modified Files Dialog ═══
    if (BridgeState.showModifiedFilesDialog) {
        ModifiedFilesDialog(
            onDismissRequest = { BridgeState.showModifiedFilesDialog = false }
        )
    }

    // ═══ APK Build & OTA Dialog ═══
    if (BridgeState.showApkBuildDialog) {
        ApkBuildDialog(
            onDismissRequest = { BridgeState.showApkBuildDialog = false }
        )
    }

    var showElementPanel by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(BridgeState.snackbarMessage) {
        BridgeState.snackbarMessage?.let { msg ->
            snackbarHostState.showSnackbar(msg)
            BridgeState.snackbarMessage = null
        }
    }

    LaunchedEffect(DesignModeRegistry.selectedSourceFile, DesignModeRegistry.selectedSourceLine) {
        val file = DesignModeRegistry.selectedSourceFile
        val line = DesignModeRegistry.selectedSourceLine
        if (file != null && line > 0) {
            showElementPanel = true
            BridgeState.isLoadingElementColors = true
            BridgeState.elementAnalysisError = null

            // 3-second timeout for element color loading
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
                BridgeState.elementColors.clear()
                BridgeState.elementDimensions.clear()
                BridgeState.elementTexts.clear()
                BridgeState.elementComposableName = ""
                BridgeState.isLoadingElementColors = false
                DesignModeRegistry.selectedSourceFile = null
                DesignModeRegistry.selectedSourceLine = 0
            },
            sheetState = sheetState,
        ) {
            if (BridgeState.isLoadingElementColors) {
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

                    Spacer(Modifier.height(8.dp))

                    // ═══ Mode Header & Switcher Tabs ═══
                    val currentMode = BridgeState.currentEditMode
                    val modeTitle = when (currentMode) {
                        EditMode.COLOR -> "🎨 Element Colors (Color Mode)"
                        EditMode.DIMENSION -> "📏 Element Dimensions (Dimension Mode)"
                        EditMode.TEXT -> "📝 Element Text (Text Mode)"
                    }

                    Surface(
                        color = when (currentMode) {
                            EditMode.COLOR -> Color(0xFF6366F1).copy(alpha = 0.15f)
                            EditMode.DIMENSION -> Color(0xFF0EA5E9).copy(alpha = 0.15f)
                            EditMode.TEXT -> Color(0xFFF59E0B).copy(alpha = 0.15f)
                        },
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = modeTitle,
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = when (currentMode) {
                                EditMode.COLOR -> Color(0xFF818CF8)
                                EditMode.DIMENSION -> Color(0xFF38BDF8)
                                EditMode.TEXT -> Color(0xFFFBBF24)
                            },
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                        )
                    }

                    Spacer(Modifier.height(8.dp))

                    // ═══ Mode-specific Content Sections ═══
                    when (currentMode) {
                        EditMode.COLOR -> ColorEditPanel()
                        EditMode.DIMENSION -> DimensionEditPanel()
                        EditMode.TEXT -> TextEditPanel()
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

    // ═══ External Modification Warning Dialog ═══
    ExternalWarningDialog()

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
