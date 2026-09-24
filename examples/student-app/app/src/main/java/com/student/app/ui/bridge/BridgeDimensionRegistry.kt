package com.student.app.ui.bridge

import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

object BridgeDimensionRegistry {

 private val overrides = mutableStateMapOf<String, Dp>()

 fun get(key: String, default: Dp): Dp {
 return overrides[key] ?: default
 }

 fun setOverride(key: String, value: Dp) {
 overrides[key] = value
 println("[BridgeDimensionRegistry] 📏 $key = $value")
 }

 fun clearAll() {
 overrides.clear()
 println("[BridgeDimensionRegistry] ♻️ All overrides cleared")
 }
}