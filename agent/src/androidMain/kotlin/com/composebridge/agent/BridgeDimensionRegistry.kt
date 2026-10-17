package com.composebridge.agent

import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

object BridgeDimensionRegistry {

    private val overrides = mutableStateMapOf<String, Dp>()
    private val _version = mutableStateOf(0L)
    val version: State<Long> get() = _version

    fun get(key: String, default: Dp): Dp {
        _version.value  // ⭐ Read to trigger recomposition
        return overrides[key] ?: default
    }

    fun setOverride(key: String, value: Float) {
        setOverride(key, value.dp)
    }

    fun setOverride(key: String, value: Dp) {
        overrides[key] = value
        _version.value = System.currentTimeMillis()
        println("[BridgeDimensionRegistry] 📏 $key = $value")
    }

    fun clearAll() {
        overrides.clear()
        _version.value = System.currentTimeMillis()
        println("[BridgeDimensionRegistry] ♻️ All overrides cleared")
    }
}
