package com.student.app.ui.bridge

import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.ui.graphics.Color

object BridgeThemeRegistry {

 private val colorMap = mutableStateMapOf<String, Color>()

 fun getColor(key: String, default: Color): Color {
 return colorMap[key] ?: default
 }

 fun setColorHex(key: String, hex: String): Boolean {
 return try {
 val cleaned = hex.removePrefix("#").removePrefix("0x").removePrefix("0X").trim()
 val argb = if (cleaned.length == 6) "FF$cleaned" else cleaned
 val color = Color(argb.toLong(16))
 colorMap[key] = color
 println("[BridgeThemeRegistry] 🎨 $key = $color")
 true
 } catch (e: Exception) {
 println("[BridgeThemeRegistry] ❌ Failed: ${e.message}")
 false
 }
 }

 fun clearAll() {
 colorMap.clear()
 println("[BridgeThemeRegistry] ♻️ All color overrides cleared")
 }
}