package com.composebridge.agent

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * BridgeState — Central container for editable Compose properties.
 *
 * Principle: Every editable property is mutableStateOf.
 * When a value changes, Compose recomposes immediately.
 *
 * Used by:
 *  1. WebSocket listener — to update values from Python bridge
 *  2. UI screens — to read and display values
 */
object BridgeState {

    // ═══ Pending Edits Queue ═══
    val pendingEdits = mutableStateListOf<PendingEdit>()
    val previewColors = mutableStateMapOf<String, String>()
    var syncInProgress by mutableStateOf(false)
    var snackbarMessage: String? by mutableStateOf(null)
    var batchMessage: String? by mutableStateOf(null)

    val pendingCount: Int get() = pendingEdits.size

    fun showSnackbar(msg: String) {
        snackbarMessage = msg
    }

    fun addPendingEdit(edit: PendingEdit) {
        pendingEdits.removeAll { existing ->
            (existing.id == edit.id) ||
            (existing.file.isNotEmpty() && existing.file == edit.file && existing.line == edit.line &&
                (existing.property == edit.property || existing.property == "all" || edit.property == "all")) ||
            (existing.tokenName.isNotEmpty() && existing.tokenName == edit.tokenName && existing.property == edit.property)
        }
        pendingEdits.add(edit)
        previewColors[edit.tokenName] = edit.newValue
        BridgeThemeRegistry.setColorHex(edit.tokenName, edit.newValue)
    }

    fun removePendingEdit(id: String) {
        val edit = pendingEdits.find { it.id == id } ?: return
        pendingEdits.remove(edit)
        previewColors.remove(edit.tokenName)
        BridgeThemeRegistry.setColorHex(edit.tokenName, edit.oldValue)
    }

    fun onBatchAck(allReceivedIds: Set<String>) {
        pendingEdits.removeAll { it.id in allReceivedIds }
        if (pendingEdits.isEmpty()) {
            previewColors.clear()
        }
        syncInProgress = false
    }

    fun clearPendingEdits(revert: Boolean = true) {
        if (revert) {
            pendingEdits.forEach { edit ->
                BridgeThemeRegistry.setColorHex(edit.tokenName, edit.oldValue)
            }
        }
        pendingEdits.clear()
        previewColors.clear()
        syncInProgress = false
    }

    // ========================================
    // Card in LazyColumn
    // ========================================

    /** Card padding */
    var cardPadding: Dp by mutableStateOf(16.dp)

    /** Card corner radius */
    var cardCornerRadius: Dp by mutableStateOf(12.dp)

    /** Card background color */
    var cardBackgroundColor: Color by mutableStateOf(Color(0xFFFFFFFF))

    // ========================================
    // Text inside Card
    // ========================================

    /** User name font size */
    var userNameFontSize: TextUnit by mutableStateOf(18.sp)

    /** User name text color */
    var userNameColor: Color by mutableStateOf(Color(0xFF000000))

    // ========================================
    // Main Title
    // ========================================

    /** Title text */
    var titleText: String by mutableStateOf("Users")

    /** Title font size */
    var titleFontSize: TextUnit by mutableStateOf(24.sp)

    /** Title color */
    var titleColor: Color by mutableStateOf(Color(0xFF000000))

    // ========================================
    // Main Column
    // ========================================

    /** Main Column padding */
    var columnPadding: Dp by mutableStateOf(0.dp)

    // ========================================
    // Spacer between title and LazyColumn
    // ========================================

    /** Spacer height */
    var spacerHeight: Dp by mutableStateOf(16.dp)

    // ========================================
    // Theme Colors & Typography Extension Delegates
    // ========================================

    /** Standalone theme color listener */
    var onThemeColorUpdate: ((String, String) -> Boolean)? = null
    var onThemeColorReset: (() -> Unit)? = null

    /** Typography update callback */
    var onTypographyUpdate: ((String, String, String) -> Boolean)? = null

    /** Dimension Token update callback */
    var onDimensionOverride: ((String, Float) -> Unit)? = null

    /** Callback invoked when tokens list is received from Python bridge */
    var onThemeTokensReceived: ((String) -> Unit)? = null

    /** Callback on element analysis received */
    var onElementAnalyzed: ((String) -> Unit)? = null

    /** Callback on edit_dimension completion */
    var onEditDimensionAck: ((Boolean, String) -> Unit)? = null

    // ═══ Focus Mode — Selected element colors ═══
    val elementColors = mutableStateListOf<ElementColorInfo>()
    val elementDimensions = mutableStateListOf<ElementDimensionInfo>()
    var showDimensionDialog: Boolean by mutableStateOf(false)
    var dimensionPending: ElementDimensionInfo? by mutableStateOf(null)
    var dimensionNewValue: Float? by mutableStateOf(null)
    var isLoadingElementColors by mutableStateOf(false)
    var currentRequestId by mutableStateOf(0L)
    var elementComposableName by mutableStateOf("Element")
    var elementAnalysisError by mutableStateOf<String?>(null)

    var onSplitTokenSuccess: ((String) -> Unit)? = null

    // ⭐ Hardcoded dialog state
    var showHardcodedDialog: Boolean by mutableStateOf(false)
    var hardcodedColorPending: ElementColorInfo? by mutableStateOf(null)
    var hardcodedNewHex: String? by mutableStateOf(null)

    // ⭐ Hardcoded info
    var hardcodedUsageGlobal: Int by mutableStateOf(0)
    var hardcodedLocations: List<ElementColorLocation> by mutableStateOf(emptyList())

    // ⭐ Rebuild Status
    var pendingRebuild: Boolean by mutableStateOf(false)
    var lastGlobalEditInfo: String? by mutableStateOf(null)

    // ═══ Global Edit Anti-Bounce ═══
    var lastGlobalEditToken: String? = null
    var lastGlobalEditColor: String? = null
    var lastGlobalEditTime: Long = 0L

    fun clearElementColors() {
        elementColors.clear()
        elementDimensions.clear()
        isLoadingElementColors = false
        elementComposableName = "Element"
        elementAnalysisError = null
        showHardcodedDialog = false
        hardcodedColorPending = null
        hardcodedNewHex = null
        showDimensionDialog = false
        dimensionPending = null
        dimensionNewValue = null
    }

    // ═══ Agent Status ═══
    private var _agentBusy by mutableStateOf(false)
    /** Is agent busy? */
    val agentBusy: Boolean get() = _agentBusy

    private var _queueCount by mutableStateOf(0)
    /** Pending edits queue count */
    val queueCount: Int get() = _queueCount

    /** Last queue count value */
    var lastQueueUpdate: Long by mutableStateOf(0L)
        private set

    /** Update agent_busy from WebSocket message */
    fun setAgentBusy(busy: Boolean) {
        _agentBusy = busy
        lastQueueUpdate = System.currentTimeMillis()
        println("[BridgeState] 🤖 Agent busy: $busy")
    }

    /** Update queue count */
    fun setQueueCount(count: Int) {
        _queueCount = count
        lastQueueUpdate = System.currentTimeMillis()
        println("[BridgeState] 📥 Queue: $count edits")
    }

    /** UI Callbacks */
    var onAgentStatusChanged: ((Boolean) -> Unit)? = null
    var onQueueCountChanged: ((Int) -> Unit)? = null

    // ═══ Sync Status ═══
    private var _syncing by mutableStateOf(false)
    val syncing: Boolean get() = _syncing

    private var _syncResultMessage by mutableStateOf<String?>(null)
    val syncResultMessage: String? get() = _syncResultMessage

    fun setSyncing(value: Boolean) {
        _syncing = value
        println("[BridgeState] ⏳ Syncing: $value")
    }

    fun setSyncResult(message: String?) {
        _syncResultMessage = message
        println("[BridgeState] 📢 Sync result: $message")
    }

    fun clearSyncResult() {
        _syncResultMessage = null
    }

    fun requestQueueStatus(): Boolean {
        return ComposeBridgeAgent.requestQueueStatus()
    }

    // ========================================
    // Baseline — Original values on app launch
    // ========================================

    /** Is baseline saved? */
    private var baselineCaptured: Boolean = false

    /** Original baseline values */
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
     * Saves current values as baseline.
     * Called once on app startup.
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
     * Restores original values and clears pending changes.
     * Called when Design Mode is disabled.
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
        // ⚠️ Do not reset dimension overrides — they are persisted in BridgeSpacing.kt
        println("[BridgeState] ♻️ Reverted to baseline (dimensions kept)")
    }

    // ========================================
    // Track pending changes (not yet sent)
    // ========================================

    /**
     * Map: Property name -> New pending value.
     * Populated on edits, cleared on sync.
     */
    val pendingChanges = mutableStateMapOf<String, String>()

    /** Are there pending changes? */
    fun hasPendingChanges(): Boolean = pendingChanges.isNotEmpty()

    /**
     * Register pending change.
     */
    fun markPending(property: String, value: String) {
        pendingChanges[property] = value
    }

    /**
     * Clear pending changes (after sync).
     */
    fun clearPending() {
        pendingChanges.clear()
    }

    // ========================================
    // Utility
    // ========================================

    /** Reset all values to default */
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

    /** Returns snapshot of current values for diagnostics */
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
     * Applies a single update from Python bridge.
     *
     * @param property Property name (e.g. "cardPadding")
     * @param value New value as string (e.g. "60")
     * @return true if applied, false if property unknown
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
                    // ⭐ Typography — do not fall through to Color
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
                            // ⚠️ Important: always return here — do not fall through to Color
                            return handled
                        } else {
                            println("[BridgeState] ❌ Invalid typography property format: $property")
                            return false
                        }
                    }

                    // ⭐ Colors
                    if (property.startsWith("AppColors.")) {
                        val key = property.removePrefix("AppColors.")
                        BridgeThemeRegistry.setColorHex(key, value)
                        val handled = onThemeColorUpdate?.invoke(key, value) ?: true
                        if (handled) {
                            println("[BridgeState] 🎨 Theme color updated: $key = $value")
                            return true
                        } else {
                            println("[BridgeState] ❌ Color update failed: $key")
                            return false
                        }
                    }

                    // Unknown property
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
     * Converts hex string to Color.
     * Accepts: "#FFFFFF", "0xFFFFFFFF", or "FFFFFFFF"
     */
    private fun parseColor(hex: String): Color {
        val cleaned = hex
            .removePrefix("#")
            .removePrefix("0x")
            .removePrefix("0X")
            .trim()

        // If 6 characters -> RGB without alpha
        val argb = if (cleaned.length == 6) {
            "FF$cleaned"
        } else {
            cleaned
        }

        return Color(argb.toLong(16))
    }
}

data class ElementColorOccurrence(
    val line: Int,
    val property: String,
)

data class ElementColorLocation(
    val file: String,
    val line: Int,
    val property: String = "",
)

data class ElementColorInfo(
    val name: String,
    val value: String,
    val usageGlobal: Int,
    val usageInElement: Int,
    val isShared: Boolean,
    val isToken: Boolean,
    val property: String,
    val lineInElement: Int,
    val occurrencesInElement: List<ElementColorOccurrence> = emptyList(),
    val locations: List<ElementColorLocation> = emptyList(),
    val isThemeDependent: Boolean = false,
)

data class ElementDimensionInfo(
    val property: String,
    val value: String,
    val number: Float,
    val kind: String,          // "dp" | "sp"
    val line: Int,
    val defaultValue: Float,
    val currentValue: Float,
    val isTernary: Boolean = false,
    val desktopValue: Float? = null,
    val mobileValue: Float? = null,
    val usageGlobal: Int = 0,
    val isShared: Boolean = false,
    val locations: List<ElementColorLocation> = emptyList(),
    val file: String = "",
    val inSharedFunction: Boolean = false,
    val functionName: String = "",
    val functionCallCount: Int = 0,
    val registryKey: String = "",
    val isRegistryWrapped: Boolean = false,
)

data class PendingEdit(
    val id: String = java.util.UUID.randomUUID().toString(),
    val type: String,             // "global_color" | "split_token" | "dimension"
    val file: String,
    val line: Int,
    val property: String = "all", // "all" | "c1" | "c2" | "background" ...
    val oldValue: String,
    val newValue: String,
    val tokenName: String,
    val timestamp: Long = System.currentTimeMillis(),
    val originalToken: String? = null,
    val occurrences: List<ElementColorOccurrence> = emptyList(),
    val dimensionToken: String? = null,
    val dimensionValue: Float? = null,
    val occurrencesJson: String? = null,
    val originalValue: String? = null,
    val isTernary: Boolean = false,
    val desktopValue: Float? = null,
    val isShared: Boolean = false,
    val editMode: String = "split",  // "split" | "global"
    val dimensionKind: String = "dp",
    val registryKey: String = "",
)
