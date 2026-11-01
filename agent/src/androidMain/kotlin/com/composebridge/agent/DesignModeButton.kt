package com.composebridge.agent

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun DesignModeButton(modifier: Modifier = Modifier) {
    val isActive = DesignModeRegistry.isActive
    val currentMode = BridgeState.currentMode

    DisposableEffect(isActive) {
        onDispose {
            BridgeOverlayManager.updateToolbarBounds(null)
        }
    }

    if (!isActive) {
        FloatingActionButton(
            onClick = { DesignModeRegistry.toggle() },
            modifier = modifier
                .size(46.dp)
                .onGloballyPositioned { coords ->
                    val pos = coords.positionInRoot()
                    val size = coords.size
                    BridgeOverlayManager.updateToolbarBounds(
                        android.graphics.Rect(
                            (pos.x - 14).toInt(),
                            (pos.y - 14).toInt(),
                            (pos.x + size.width + 14).toInt(),
                            (pos.y + size.height + 14).toInt()
                        )
                    )
                },
            containerColor = Color(0xFF7C3AED),
            elevation = FloatingActionButtonDefaults.elevation(6.dp),
            shape = CircleShape
        ) {
            Text(
                text = "🎨",
                fontSize = 20.sp
            )
        }
    } else {
        Column(
            modifier = modifier
                .onGloballyPositioned { coords ->
                    val pos = coords.positionInRoot()
                    val size = coords.size
                    BridgeOverlayManager.updateToolbarBounds(
                        android.graphics.Rect(
                            (pos.x - 14).toInt(),
                            (pos.y - 14).toInt(),
                            (pos.x + size.width + 14).toInt(),
                            (pos.y + size.height + 14).toInt()
                        )
                    )
                }
                .clip(RoundedCornerShape(22.dp))
                .background(Color(0xEE0F172A))
                .border(1.dp, Color(0x33FFFFFF), RoundedCornerShape(22.dp))
                .padding(vertical = 8.dp, horizontal = 5.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // ✕ Close Button
            SmallFloatingActionButton(
                onClick = { DesignModeRegistry.toggle() },
                containerColor = Color(0xFFEF4444),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(38.dp)
            ) {
                Text(text = "✕", fontSize = 15.sp, color = Color.White, fontWeight = FontWeight.Bold)
            }

            // 🌍 Remote Access Button
            SmallFloatingActionButton(
                onClick = {
                    BridgeState.showRemoteDialog = true
                },
                containerColor = if (BridgeState.isConnected) Color(0xFF059669) else Color(0xFF1E293B),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(38.dp)
            ) {
                Text(text = "🌍", fontSize = 16.sp)
            }

            // 📦 Build & Install APK Button
            SmallFloatingActionButton(
                onClick = {
                    android.util.Log.d("ComposeBridge", "📦 [DesignModeButton] Build & Install button clicked")
                    BridgeState.showApkBuildDialog = true
                    if (!BridgeState.isBuildingApk && BridgeState.apkBuildStage != "done" && BridgeState.apkBuildStage != "downloaded") {
                        ComposeBridgeAgent.buildAndSendApk(forceRebuild = false)
                    }
                },
                containerColor = if (BridgeState.isBuildingApk) Color(0xFFD97706) else Color(0xFF2563EB),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(38.dp)
            ) {
                if (BridgeState.isBuildingApk) {
                    CircularProgressIndicator(
                        color = Color.White,
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp
                    )
                } else {
                    Text(text = "📦", fontSize = 16.sp)
                }
            }

            // 📁 Changes / Modified Files Button
            Box(contentAlignment = Alignment.Center) {
                SmallFloatingActionButton(
                    onClick = {
                        android.util.Log.d("ComposeBridge", "📁 [DesignModeButton] Changes button clicked")
                        BridgeState.showModifiedFilesDialog = true
                        ComposeBridgeAgent.requestModifiedFiles()
                    },
                    containerColor = if (BridgeState.modifiedFiles.isNotEmpty()) Color(0xFFD97706) else Color(0xFF1E293B),
                    contentColor = Color.White,
                    shape = CircleShape,
                    modifier = Modifier.size(38.dp)
                ) {
                    Text(text = "📁", fontSize = 16.sp)
                }

                if (BridgeState.modifiedFiles.isNotEmpty()) {
                    Box(
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .offset(x = 3.dp, y = (-3).dp)
                            .clip(CircleShape)
                            .background(Color(0xFFEF4444))
                            .padding(horizontal = 4.dp, vertical = 1.dp)
                    ) {
                        Text(
                            text = "${BridgeState.modifiedFiles.size}",
                            fontSize = 9.sp,
                            color = Color.White,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            // 🔄 Sync Button
            Box(contentAlignment = Alignment.Center) {
                SmallFloatingActionButton(
                    onClick = {
                        val edits = BridgeState.pendingEdits.toList()
                        if (edits.isNotEmpty() && !BridgeState.syncInProgress) {
                            BridgeState.syncInProgress = true
                            BridgeState.showSnackbar("⏳ Syncing ${edits.size} edit(s)...")
                            ComposeBridgeAgent.sendBatchEdits(edits)
                        } else if (edits.isEmpty()) {
                            BridgeState.showSnackbar("✨ No pending edits to sync")
                        }
                    },
                    containerColor = if (BridgeState.pendingCount > 0) Color(0xFF10B981) else Color(0xFF1E293B),
                    contentColor = Color.White,
                    shape = CircleShape,
                    modifier = Modifier.size(38.dp)
                ) {
                    if (BridgeState.syncInProgress) {
                        CircularProgressIndicator(
                            color = Color.White,
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text(text = "🔄", fontSize = 16.sp)
                    }
                }

                // Badge for pending edits count
                if (BridgeState.pendingCount > 0) {
                    Box(
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .offset(x = 3.dp, y = (-3).dp)
                            .clip(CircleShape)
                            .background(Color(0xFFEF4444))
                            .padding(horizontal = 4.dp, vertical = 1.dp)
                    ) {
                        Text(
                            text = "${BridgeState.pendingCount}",
                            fontSize = 9.sp,
                            color = Color.White,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            // ✏️ Text Mode
            SmallFloatingActionButton(
                onClick = {
                    BridgeState.currentMode = EditMode.TEXT
                    BridgeState.showSnackbar("✏️ Text Edit Mode")
                },
                containerColor = if (currentMode == EditMode.TEXT) Color(0xFFF59E0B) else Color(0xFF1E293B),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(38.dp)
            ) {
                Text(text = "✏️", fontSize = 16.sp)
            }

            // 📐 Dimensions Mode
            SmallFloatingActionButton(
                onClick = {
                    BridgeState.currentMode = EditMode.DIMENSION
                    BridgeState.showSnackbar("📐 Dimension Edit Mode")
                },
                containerColor = if (currentMode == EditMode.DIMENSION) Color(0xFF0EA5E9) else Color(0xFF1E293B),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(38.dp)
            ) {
                Text(text = "📐", fontSize = 16.sp)
            }

            // 🎨 Colors Mode
            SmallFloatingActionButton(
                onClick = {
                    BridgeState.currentMode = EditMode.COLOR
                    BridgeState.showSnackbar("🎨 Color Edit Mode")
                },
                containerColor = if (currentMode == EditMode.COLOR) Color(0xFF6366F1) else Color(0xFF1E293B),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(38.dp)
            ) {
                Text(text = "🎨", fontSize = 16.sp)
            }
        }
    }
}
