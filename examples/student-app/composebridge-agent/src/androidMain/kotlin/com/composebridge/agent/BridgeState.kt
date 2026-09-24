package com.composebridge.agent

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * BridgeState — Container Compose .
 *
 * : mutableStateOf.
 * → Compose .
 *
 * :
 * 1. WebSocket listener — Python
 * 2. HomeScreenForTest — 
 */
object BridgeState {

 // ========================================
 // Card — LazyColumn
 // ========================================

 /** Padding around card */
 var cardPadding: Dp by mutableStateOf(16.dp)

 /** cornerRadius */
 var cardCornerRadius: Dp by mutableStateOf(12.dp)

 /** Card background color */
 var cardBackgroundColor: Color by mutableStateOf(Color(0xFFFFFFFF))

 // ========================================
 // Text — 
 // ========================================

 /** Username font size */
 var userNameFontSize: TextUnit by mutableStateOf(18.sp)

 /** */
 var userNameColor: Color by mutableStateOf(Color(0xFF000000))

 // ========================================
 // Title — 
 // ========================================

 /** */
 var titleText: String by mutableStateOf("Users")

 /** Title font size */
 var titleFontSize: TextUnit by mutableStateOf(24.sp)

 /** Title color */
 var titleColor: Color by mutableStateOf(Color(0xFF000000))

 // ========================================
 // Column — 
 // ========================================

 /** padding */
 var columnPadding: Dp by mutableStateOf(0.dp)

 // ========================================
 // Spacer — LazyColumn
 // ========================================

 /** */
 var spacerHeight: Dp by mutableStateOf(16.dp)

 // ========================================
 // Theme Colors & Typography Extension Delegates
 // ========================================

 /** */
 var onThemeColorUpdate: ((String, String) -> Boolean)? = null
 var onThemeColorReset: (() -> Unit)? = null

 /** callback Typography */
 var onTypographyUpdate: ((String, String, String) -> Boolean)? = null

 /** callback Dimension Token */
 var onDimensionOverride: ((String, Float) -> Unit)? = null

 /** callback Python */
 var onThemeTokensReceived: ((String) -> Unit)? = null

 /** callback Analyze */
 var onElementAnalyzed: ((String) -> Unit)? = null

 /** callback edit_dimension */
 var onEditDimensionAck: ((Boolean, String) -> Unit)? = null

 // ========================================
 // Baseline — Apply
 // ========================================

 /** baseline */
 private var baselineCaptured: Boolean = false

 /** */
 private var baselinePadding: Dp = 16.dp
 private var baselineCornerRadius: Dp = 12.dp
 private var baselineBgColor: Color = Color(0xFFFFFFFF)
 private var baselineUserFontSize: TextUnit = 18.sp
 private var baselineUserColor: Color = Color(0xFF000000)
 private var baselineTitle: String = "Users"
 private var baselineTitleFontSize: TextUnit = 24.sp
 private var baselineTitleColor: Color = Color(0xFF000000)
 private var baselineColumnPadding: Dp = 0.dp
 private var baselineSpacerHeight: Dp = 16.dp

 /**
 * baseline.
 * Apply.
 */
 fun captureBaseline(force: Boolean = false) {
 if (baselineCaptured && !force) return
 baselinePadding = cardPadding
 baselineCornerRadius = cardCornerRadius
 baselineBgColor = cardBackgroundColor
 baselineUserFontSize = userNameFontSize
 baselineUserColor = userNameColor
 baselineTitle = titleText
 baselineTitleFontSize = titleFontSize
 baselineTitleColor = titleColor
 baselineColumnPadding = columnPadding
 baselineSpacerHeight = spacerHeight
 baselineCaptured = true
 println("[BridgeState] ✅ Baseline captured${if (force) " (updated)" else ""}")
 }

 /**
 * .
 * Design Mode.
 */
 fun revertToBaseline() {
 cardPadding = baselinePadding
 cardCornerRadius = baselineCornerRadius
 cardBackgroundColor = baselineBgColor
 userNameFontSize = baselineUserFontSize
 userNameColor = baselineUserColor
 titleText = baselineTitle
 titleFontSize = baselineTitleFontSize
 titleColor = baselineTitleColor
 columnPadding = baselineColumnPadding
 spacerHeight = baselineSpacerHeight
 pendingChanges.clear()
 onThemeColorReset?.invoke()
 // ⚠️ dimension overrides — BridgeSpacing.kt
 println("[BridgeState] ♻️ Reverted to baseline (dimensions kept)")
 }

 // ========================================
 // ( )
 // ========================================

 /**
 * : → .
 * Edit .
 */
 val pendingChanges = mutableStateMapOf<String, String>()

 /** */
 fun hasPendingChanges(): Boolean = pendingChanges.isNotEmpty()

 /**
 * .
 */
 fun markPending(property: String, value: String) {
 pendingChanges[property] = value
 }

 /**
 * ( ).
 */
 fun clearPending() {
 pendingChanges.clear()
 }

 // ========================================
 // Utility
 // ========================================

 /** */
 fun reset() {
 cardPadding = 16.dp
 cardCornerRadius = 12.dp
 cardBackgroundColor = Color(0xFFFFFFFF)
 userNameFontSize = 18.sp
 userNameColor = Color(0xFF000000)
 titleText = "Users"
 titleFontSize = 24.sp
 titleColor = Color(0xFF000000)
 columnPadding = 0.dp
 spacerHeight = 16.dp
 clearPending()
 onThemeColorReset?.invoke()
 }

 /** (snapshot) - */
 fun snapshot(): String {
 return """
 BridgeState snapshot:
 cardPadding = $cardPadding
 cardCornerRadius = $cardCornerRadius
 cardBackgroundColor = $cardBackgroundColor
 userNameFontSize = $userNameFontSize
 userNameColor = $userNameColor
 titleText = "$titleText"
 titleFontSize = $titleFontSize
 titleColor = $titleColor
 columnPadding = $columnPadding
 spacerHeight = $spacerHeight
 """.trimIndent()
 }

 /**
 * Python.
 *
 * @param property ( "cardPadding")
 * @param value ( "60")
 * @return true Apply false Unknown 
 */
 fun applyUpdate(property: String, value: String): Boolean {
 return try {
 when (property) {
 // Card
 "cardPadding" -> {
 cardPadding = value.toFloat().dp
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }
 "cardCornerRadius" -> {
 cardCornerRadius = value.toFloat().dp
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }
 "cardBackgroundColor" -> {
 cardBackgroundColor = parseColor(value)
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }

 // User name
 "userNameFontSize" -> {
 userNameFontSize = value.toFloat().sp
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }
 "userNameColor" -> {
 userNameColor = parseColor(value)
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }

 // Title
 "titleText" -> {
 titleText = value
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }
 "titleFontSize" -> {
 titleFontSize = value.toFloat().sp
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }
 "titleColor" -> {
 titleColor = parseColor(value)
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }

 // Column
 "columnPadding" -> {
 columnPadding = value.toFloat().dp
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }

 // Spacer
 "spacerHeight" -> {
 spacerHeight = value.toFloat().dp
 println("[BridgeState] ✅ Updated: $property = $value")
 true
 }

 else -> {
 // ⭐ Typography — Color
 if (property.startsWith("AppTypography.")) {
 val parts = property.removePrefix("AppTypography.").split(".")
 if (parts.size == 2) {
 val styleKey = parts[0]
 val propName = parts[1]
 val handled = onTypographyUpdate?.invoke(styleKey, propName, value) ?: false
 if (handled) {
 println("[BridgeState] 📝 Typography updated: $styleKey.$propName = $value")
 } else {
 println("[BridgeState] ❌ Typography update failed: $styleKey.$propName (registry returned false)")
 }
 // ⚠️ : — Color
 return handled
 } else {
 println("[BridgeState] ❌ Invalid typography property format: $property")
 return false
 }
 }

 // ⭐ Colors
 if (property.startsWith("AppColors.")) {
 val key = property.removePrefix("AppColors.")
 val handled = onThemeColorUpdate?.invoke(key, value) ?: false
 if (handled) {
 println("[BridgeState] 🎨 Theme color updated: $key = $value")
 return true
 } else {
 println("[BridgeState] ❌ Color update failed: $key")
 return false
 }
 }

 // Unknown
 println("[BridgeState] ❌ Unknown property: $property")
 false
 }
 }
 } catch (e: Exception) {
 println("[BridgeState] ❌ Failed to apply $property=$value: ${e.message}")
 false
 }
 }

 /**
 * hex Color.
 * : "#FFFFFF" "0xFFFFFFFF" "FFFFFFFF"
 */
 private fun parseColor(hex: String): Color {
 val cleaned = hex
 .removePrefix("#")
 .removePrefix("0x")
 .removePrefix("0X")
 .trim()

 // 6 → RGB alpha
 val argb = if (cleaned.length == 6) {
 "FF$cleaned"
 } else {
 cleaned
 }

 return Color(argb.toLong(16))
 }
}