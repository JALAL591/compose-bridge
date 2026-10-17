package com.composebridge.agent

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun DesignModeButton(modifier: Modifier = Modifier) {
    val isActive = DesignModeRegistry.isActive
    
    FloatingActionButton(
        onClick = { DesignModeRegistry.toggle() },
        modifier = modifier,
        containerColor = if (isActive) Color(0xFFEF4444) else Color(0xFF7C3AED)
    ) {
        Text(
            text = if (isActive) "✕" else "🎨",
            fontSize = 20.sp,
            color = Color.White
        )
    }
}
