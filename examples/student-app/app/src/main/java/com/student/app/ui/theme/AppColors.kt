package com.student.app.ui.theme

import androidx.compose.ui.graphics.Color
import com.student.app.ui.bridge.BridgeThemeRegistry

object AppColors {
 val Primary: Color
 get() = BridgeThemeRegistry.getColor("Primary", Color(0xFFEC4899))

 val PrimaryGradientEnd: Color
 get() = BridgeThemeRegistry.getColor("PrimaryGradientEnd", Color(0xFF3B82F6))

 val AccentOrange: Color
 get() = BridgeThemeRegistry.getColor("AccentOrange", Color(0xFF10B981))

 val AccentGreen: Color
 get() = BridgeThemeRegistry.getColor("AccentGreen", Color(0xFF10B981))

 val AccentPurple: Color
 get() = BridgeThemeRegistry.getColor("AccentPurple", Color(0xFF10B981))

 val Surface: Color
 get() = BridgeThemeRegistry.getColor("Surface", Color(0xFFFFFFFF))

 val Background: Color
 get() = BridgeThemeRegistry.getColor("Background", Color(0xFFF8FAFC))

 val TextPrimary: Color
 get() = BridgeThemeRegistry.getColor("TextPrimary", Color(0xFF0F172A))

 val TextSecondary: Color
 get() = BridgeThemeRegistry.getColor("TextSecondary", Color(0xFF64748B))

 val TextLight: Color
 get() = BridgeThemeRegistry.getColor("TextLight", Color(0xFFFFFFFF))
}