package com.student.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.composebridge.agent.BridgeState
import com.composebridge.agent.ComposeBridgeAgent
import com.composebridge.agent.DesignModeRegistry
import com.student.app.ui.bridge.BridgeDimensionRegistry
import com.student.app.ui.bridge.BridgeThemeRegistry
import com.student.app.ui.pages.DashboardPage
import com.student.app.ui.panels.GlobalPanels
import com.student.app.ui.theme.AppColors

class MainActivity : ComponentActivity() {
 override fun onCreate(savedInstanceState: Bundle?) {
 super.onCreate(savedInstanceState)

 // ⭐ Wire-up ComposeBridge
 BridgeState.onThemeColorUpdate = { key, hex ->
 BridgeThemeRegistry.setColorHex(key, hex)
 }
 BridgeState.onDimensionOverride = { key, value ->
 BridgeDimensionRegistry.setOverride(key, value.dp)
 }

 // ⭐ WebSocket
 ComposeBridgeAgent.start("ws://127.0.0.1:8711")

 setContent {
 MaterialTheme {
 Surface(color = AppColors.Background) {
 ComposeBridgeAgent.Root {
 Box(modifier = Modifier.fillMaxSize()) {
 DashboardPage()
 
 // ⭐ Design Mode 
 DesignModeButton(
 modifier = Modifier
 .align(Alignment.TopEnd)
 .padding(16.dp)
 )
 
 GlobalPanels()
 }
 }
 }
 }
 }

 // ⭐ Overlay
 window.decorView.post {
 ComposeBridgeAgent.attachOverlay(this)
 }
 }

 override fun onDestroy() {
 ComposeBridgeAgent.detachOverlay()
 ComposeBridgeAgent.stop()
 super.onDestroy()
 }
}

/**
 * ⭐ Floating button toggling Design Mode.
 */
@Composable
private fun DesignModeButton(modifier: Modifier = Modifier) {
 val isActive = DesignModeRegistry.isActive

 FloatingActionButton(
 onClick = {
 DesignModeRegistry.toggle()
 println("[MainActivity] 🎯 Design Mode: ${DesignModeRegistry.isActive}")
 },
 containerColor = if (isActive) Color(0xFFE53935) else Color(0xFF6366F1),
 shape = CircleShape,
 modifier = modifier,
 ) {
 Icon(
 imageVector = if (isActive) Icons.Default.Close else Icons.Default.Build,
 contentDescription = if (isActive) "Disable" else "Enable Design Mode",
 tint = Color.White,
 )
 }
}