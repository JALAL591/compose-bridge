package com.composebridge.agent

import androidx.compose.runtime.Composable
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf

object BridgeTextRegistry {

    private val textMap = mutableStateMapOf<String, String>()
    private val _version = mutableStateOf(0L)
    val version: State<Long> get() = _version

    @Composable
    fun getText(key: String, default: String): String {
        _version.value // Read to trigger recomposition
        val cleanKey = key.trim()
        val shortKey = if (cleanKey.contains(".")) cleanKey.substringAfterLast(".") else cleanKey
        return textMap[cleanKey] ?: textMap[shortKey] ?: default
    }

    fun get(key: String, default: String): String {
        _version.value
        val cleanKey = key.trim()
        val shortKey = if (cleanKey.contains(".")) cleanKey.substringAfterLast(".") else cleanKey
        return textMap[cleanKey] ?: textMap[shortKey] ?: default
    }

    fun setOverride(key: String, value: String) {
        val cleanKey = key.trim()
        textMap[cleanKey] = value
        if (cleanKey.contains(".")) {
            val shortKey = cleanKey.substringAfterLast(".")
            textMap[shortKey] = value
        }
        _version.value = System.currentTimeMillis()
        println("[BridgeTextRegistry] 📝 $cleanKey = '$value' (v=${_version.value})")
    }

    fun clearAll() {
        textMap.clear()
        _version.value = System.currentTimeMillis()
        println("[BridgeTextRegistry] 🧹 All text overrides cleared")
    }
}
