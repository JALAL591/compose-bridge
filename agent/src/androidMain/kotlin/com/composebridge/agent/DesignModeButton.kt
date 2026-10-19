package com.composebridge.agent

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.SmallFloatingActionButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun DesignModeButton(modifier: Modifier = Modifier) {
    val isActive = DesignModeRegistry.isActive
    val currentMode = BridgeState.currentMode

    if (!isActive) {
        FloatingActionButton(
            onClick = { DesignModeRegistry.toggle() },
            modifier = modifier.size(56.dp),
            containerColor = Color(0xFF7C3AED),
            elevation = FloatingActionButtonDefaults.elevation(8.dp),
            shape = CircleShape
        ) {
            Text(
                text = "🎨",
                fontSize = 22.sp
            )
        }
    } else {
        Row(
            modifier = modifier
                .clip(RoundedCornerShape(28.dp))
                .background(Color(0xCC0F172A))
                .border(1.dp, Color(0x33FFFFFF), RoundedCornerShape(28.dp))
                .padding(horizontal = 8.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // 🎨 Colors Mode
            SmallFloatingActionButton(
                onClick = {
                    BridgeState.currentMode = EditMode.COLOR
                    BridgeState.showSnackbar("🎨 Color Mode")
                },
                containerColor = if (currentMode == EditMode.COLOR) Color(0xFF6366F1) else Color(0xFF1E293B),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(42.dp)
            ) {
                Text(text = "🎨", fontSize = 18.sp)
            }

            // 📏 Dimensions Mode
            SmallFloatingActionButton(
                onClick = {
                    BridgeState.currentMode = EditMode.DIMENSION
                    BridgeState.showSnackbar("📏 Dimension Mode")
                },
                containerColor = if (currentMode == EditMode.DIMENSION) Color(0xFF0EA5E9) else Color(0xFF1E293B),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(42.dp)
            ) {
                Text(text = "📏", fontSize = 18.sp)
            }

            // 📝 Text Mode
            SmallFloatingActionButton(
                onClick = {
                    BridgeState.currentMode = EditMode.TEXT
                    BridgeState.showSnackbar("📝 Text Mode")
                },
                containerColor = if (currentMode == EditMode.TEXT) Color(0xFFF59E0B) else Color(0xFF1E293B),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(42.dp)
            ) {
                Text(text = "📝", fontSize = 18.sp)
            }

            // ✕ Close Button
            SmallFloatingActionButton(
                onClick = { DesignModeRegistry.toggle() },
                containerColor = Color(0xFFEF4444),
                contentColor = Color.White,
                shape = CircleShape,
                modifier = Modifier.size(42.dp)
            ) {
                Text(text = "✕", fontSize = 16.sp, color = Color.White)
            }
        }
    }
}
