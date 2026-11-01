/**
 * ComposeBridge Color Utilities.
 * دوال مساعدة موحدة لمعالجة وتحويل الألوان النصية Hex إلى كائنات Color في Compose.
 */
package com.composebridge.agent.util

import androidx.compose.ui.graphics.Color

object ColorUtils {
    /**
     * Converts a hex color string to Compose [Color].
     * Accepts "#RRGGBB", "#AARRGGBB", "0xRRGGBB", "0xAARRGGBB", or raw hex strings.
     */
    fun parseHexColor(hex: String, fallback: Color = Color.Black): Color {
        val cleaned = hex
            .removePrefix("#")
            .removePrefix("0x")
            .removePrefix("0X")
            .trim()

        if (cleaned.isEmpty()) return fallback

        return try {
            val argb = when (cleaned.length) {
                3 -> { // Short RGB e.g. "FFF" -> "FFFFFFFF"
                    val r = cleaned[0]
                    val g = cleaned[1]
                    val b = cleaned[2]
                    "FF$r$r$g$g$b$b"
                }
                6 -> "FF$cleaned"
                8 -> cleaned
                else -> return fallback
            }
            Color(argb.toLong(16))
        } catch (_: Exception) {
            fallback
        }
    }

    /**
     * Alias for [parseHexColor].
     */
    fun hexToColor(hex: String): Color = parseHexColor(hex)
}

