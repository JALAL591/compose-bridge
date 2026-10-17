package com.composebridge.agent

import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.graphics.Color

object BridgeThemeRegistry {

    private val colorMap = mutableStateMapOf<String, Color>()
    private val _version = mutableStateOf(0L)
    val version: State<Long> get() = _version

    fun getColor(key: String, default: Color): Color {
        _version.value
        return colorMap[key] ?: default
    }

    fun setColorHex(key: String, hex: String): Boolean {
        return try {
            val cleaned = hex.removePrefix("#").removePrefix("0x").removePrefix("0X").trim()
            val argb = if (cleaned.length == 6) "FF$cleaned" else cleaned
            val color = Color(argb.toLong(16))
            colorMap[key] = color
            _version.value = System.currentTimeMillis()
            println("[BridgeThemeRegistry] 🎨 $key = $color (v=${_version.value})")
            true
        } catch (e: Exception) {
            println("[BridgeThemeRegistry] ❌ Failed: ${e.message}")
            false
        }
    }

    fun clearAll() {
        colorMap.clear()
        _version.value = System.currentTimeMillis()
        println("[BridgeThemeRegistry] ♻️ All color overrides cleared")
    }
}
