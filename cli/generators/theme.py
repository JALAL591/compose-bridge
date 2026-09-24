# -*- coding: utf-8 -*-
"""
Generates theme files — getters reading from Registries.
Live Editing enabled from day one.
"""

from pathlib import Path


def _write(package_path, relative, content):
    path = Path(package_path) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_theme(screen_json):
    package = screen_json["package"]
    package_path = screen_json["package_path"]
    theme = screen_json["theme"]

    # ═══ AppColors.kt — getters from Registry ═══
    _write(package_path, "ui/theme/AppColors.kt", f"""package {package}.ui.theme

import androidx.compose.ui.graphics.Color
import {package}.ui.bridge.BridgeThemeRegistry

/**
 * AppColors — Each color reads from BridgeThemeRegistry.
 * Can be edited directly from device.
 */
object AppColors {{
    val Primary: Color
        get() = BridgeThemeRegistry.getColor("Primary", Color(0xFF{theme['primary']}))

    val PrimaryGradientEnd: Color
        get() = BridgeThemeRegistry.getColor("PrimaryGradientEnd", Color(0xFF{theme.get('gradient_end', '3B82F6')}))

    val AccentOrange: Color
        get() = BridgeThemeRegistry.getColor("AccentOrange", Color(0xFF{theme.get('accent_orange', 'F59E0B')}))

    val AccentGreen: Color
        get() = BridgeThemeRegistry.getColor("AccentGreen", Color(0xFF{theme.get('accent_green', '10B981')}))

    val AccentPurple: Color
        get() = BridgeThemeRegistry.getColor("AccentPurple", Color(0xFF{theme.get('accent_purple', '8B5CF6')}))

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
}}
""")

    # ═══ AppDimens.kt — getters from Registry ═══
    _write(package_path, "ui/theme/AppDimens.kt", f"""package {package}.ui.theme

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import {package}.ui.bridge.BridgeDimensionRegistry

/**
 * AppDimens — Each value reads from BridgeDimensionRegistry.
 * Can be edited directly from device.
 */
object AppDimens {{
    val xs: Dp get() = BridgeDimensionRegistry.get("xs", 4.dp)
    val sm: Dp get() = BridgeDimensionRegistry.get("sm", 8.dp)
    val md: Dp get() = BridgeDimensionRegistry.get("md", 16.dp)
    val lg: Dp get() = BridgeDimensionRegistry.get("lg", 24.dp)
    val xl: Dp get() = BridgeDimensionRegistry.get("xl", 32.dp)

    val screenPadding: Dp get() = BridgeDimensionRegistry.get("screenPadding", 16.dp)

    val welcomeCardHeight: Dp get() = BridgeDimensionRegistry.get("welcomeCardHeight", 160.dp)
    val welcomeCardCorner: Dp get() = BridgeDimensionRegistry.get("welcomeCardCorner", 20.dp)
    val welcomeCardPadding: Dp get() = BridgeDimensionRegistry.get("welcomeCardPadding", 20.dp)

    val statCardHeight: Dp get() = BridgeDimensionRegistry.get("statCardHeight", 120.dp)
    val statCardCorner: Dp get() = BridgeDimensionRegistry.get("statCardCorner", 16.dp)
    val statCardIconSize: Dp get() = BridgeDimensionRegistry.get("statCardIconSize", 40.dp)
    val statCardIconInner: Dp get() = BridgeDimensionRegistry.get("statCardIconInner", 24.dp)

    val headerIconSize: Dp get() = BridgeDimensionRegistry.get("headerIconSize", 40.dp)
}}
""")

    # ═══ AppTypography.kt ═══
    _write(package_path, "ui/theme/AppTypography.kt", f"""package {package}.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val AppTypography = Typography(
    headlineLarge = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 28.sp,
        letterSpacing = 0.sp,
    ),
    headlineMedium = TextStyle(
        fontWeight = FontWeight.Bold,
        fontSize = 22.sp,
        letterSpacing = 0.sp,
    ),
    bodyLarge = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
        letterSpacing = 0.15.sp,
    ),
    bodySmall = TextStyle(
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.4.sp,
    ),
)
""")

    # ═══ AppStrings.kt ═══
    _write(package_path, "ui/theme/AppStrings.kt", f"""package {package}.ui.theme

object AppStrings {{
    const val studentName = "Siraj Abbas"
    const val studentLevel = "Level 3 - Engineering"
}}
""")

    print(f"  ✅ Theme files generated (with Live Editing)")
