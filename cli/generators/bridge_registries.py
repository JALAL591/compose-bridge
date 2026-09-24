# -*- coding: utf-8 -*-
"""
Generates small Registry files.
Does not generate Agent Module - just two simple files.
"""

from pathlib import Path


def _write(package_path, relative, content):
    path = Path(package_path) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate_bridge_registries(screen_json):
    package = screen_json["package"]
    package_path = screen_json["package_path"]

    # ═══ BridgeDimensionRegistry.kt ═══
    _write(package_path, "ui/bridge/BridgeDimensionRegistry.kt", f"""package {package}.ui.bridge

import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * BridgeDimensionRegistry — Reads and writes dimension overrides.
 * Tweak from device -> UI updates immediately.
 */
object BridgeDimensionRegistry {{

    private val overrides = mutableStateMapOf<String, Dp>()

    /**
     * Returns true value — override if present, else default.
     */
    fun get(key: String, default: Dp): Dp {{
        return overrides[key] ?: default
    }}

    /**
     * Sets override (called from Python via WebSocket).
     */
    fun setOverride(key: String, value: Dp) {{
        overrides[key] = value
        println("[BridgeDimensionRegistry] 📏 $key = $value")
    }}

    /**
     * Clears all overrides.
     */
    fun clearAll() {{
        overrides.clear()
        println("[BridgeDimensionRegistry] ♻️ All overrides cleared")
    }}
}}
""")

    # ═══ BridgeThemeRegistry.kt ═══
    _write(package_path, "ui/bridge/BridgeThemeRegistry.kt", f"""package {package}.ui.bridge

import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.ui.graphics.Color

/**
 * BridgeThemeRegistry — Reads and writes color overrides.
 * Tweak color from device -> UI updates immediately.
 */
object BridgeThemeRegistry {{

    private val colorMap = mutableStateMapOf<String, Color>()

    /**
     * Returns true color — override if present, else default.
     */
    fun getColor(key: String, default: Color): Color {{
        return colorMap[key] ?: default
    }}

    /**
     * Sets color by hex string.
     */
    fun setColorHex(key: String, hex: String): Boolean {{
        return try {{
            val cleaned = hex.removePrefix("#").removePrefix("0x").removePrefix("0X").trim()
            val argb = if (cleaned.length == 6) "FF$cleaned" else cleaned
            val color = Color(argb.toLong(16))
            colorMap[key] = color
            println("[BridgeThemeRegistry] 🎨 $key = $color")
            true
        }} catch (e: Exception) {{
            println("[BridgeThemeRegistry] ❌ Failed: ${{e.message}}")
            false
        }}
    }}

    /**
     * Clears all overrides.
     */
    fun clearAll() {{
        colorMap.clear()
        println("[BridgeThemeRegistry] ♻️ All color overrides cleared")
    }}
}}
""")

    print(f"  ✅ Bridge registries generated")
