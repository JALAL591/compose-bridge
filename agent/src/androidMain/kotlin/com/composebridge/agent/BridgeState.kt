/**
 * ComposeBridge State Coordinator.
 * الحاوية المركزية لخصائص Compose القابلة للتعديل وتنسيق الحالات المفككة.
 */
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
import com.composebridge.agent.state.ApkDeliveryState
import com.composebridge.agent.state.ConnectionState
import com.composebridge.agent.state.ElementSelectionState
import com.composebridge.agent.state.PendingEditsQueue

enum class EditMode {
    COLOR,
    DIMENSION,
    TEXT
}

data class WarningDialogInfo(
    val file: String,
    val message: String,
)

data class ModifiedFileInfo(
    val file: String,
    val name: String,
    val status: String = "modified"
)

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

data class ElementTextInfo(
    val text: String,
    val file: String,
    val line: Int,
    val property: String = "text",
    val isResourceOrRef: Boolean = false,
    val refKey: String? = null,
    val rawExpression: String? = null,
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
    val refKey: String? = null,
)

object BridgeState {
    var activeWarningDialog by mutableStateOf<WarningDialogInfo?>(null)

    var currentMode: EditMode by mutableStateOf(EditMode.COLOR)
    var currentEditMode: EditMode
        get() = currentMode
        set(value) { currentMode = value }

    // ═══ Pending Edits Queue (Delegated) ═══
    val pendingEdits get() = PendingEditsQueue.pendingEdits
    val previewColors get() = PendingEditsQueue.previewColors
    var syncInProgress by PendingEditsQueue::syncInProgress
    var snackbarMessage by PendingEditsQueue::snackbarMessage
    var batchMessage by PendingEditsQueue::batchMessage
    val pendingCount: Int get() = PendingEditsQueue.pendingCount

    fun showSnackbar(msg: String) = PendingEditsQueue.showSnackbar(msg)
    fun addPendingEdit(edit: PendingEdit) = PendingEditsQueue.addPendingEdit(edit)
    fun removePendingEdit(id: String) = PendingEditsQueue.removePendingEdit(id)
    fun onBatchAck(allReceivedIds: Set<String>) = PendingEditsQueue.onBatchAck(allReceivedIds)
    fun clearPendingEdits(revert: Boolean = true) = PendingEditsQueue.clearPendingEdits(revert)

    // ═══ WebSocket Connection Status (Delegated) ═══
    var isConnected by ConnectionState::isConnected
    var isReconnecting by ConnectionState::isReconnecting
    var connectionStatusText by ConnectionState::connectionStatusText
    var showRemoteDialog by ConnectionState::showRemoteDialog

    // ═══ Modified Files (Review & Rollback) ═══
    var modifiedFiles by mutableStateOf<List<ModifiedFileInfo>>(emptyList())
    var showModifiedFilesDialog by mutableStateOf(false)
    var isLoadingModifiedFiles by mutableStateOf(false)

    // ═══ OTA APK Build & Install (Delegated) ═══
    var showApkBuildDialog by ApkDeliveryState::showApkBuildDialog
    var isBuildingApk by ApkDeliveryState::isBuildingApk
    var apkBuildStage by ApkDeliveryState::apkBuildStage
    var apkBuildProgress by ApkDeliveryState::apkBuildProgress
    var apkBuildMessage by ApkDeliveryState::apkBuildMessage
    var apkAvailableFileName by ApkDeliveryState::apkAvailableFileName
    var apkAvailableFileSize by ApkDeliveryState::apkAvailableFileSize
    var apkAvailableTimeAgo by ApkDeliveryState::apkAvailableTimeAgo

    // ═══ Focus Mode & Element Selection (Delegated) ═══
    val elementColors get() = ElementSelectionState.elementColors
    val elementDimensions get() = ElementSelectionState.elementDimensions
    val elementTexts get() = ElementSelectionState.elementTexts
    var lastEvaluatedScreenText by ElementSelectionState::lastEvaluatedScreenText
    var showDimensionDialog by ElementSelectionState::showDimensionDialog
    var dimensionPending by ElementSelectionState::dimensionPending
    var dimensionNewValue by ElementSelectionState::dimensionNewValue
    var isLoadingElementColors by ElementSelectionState::isLoadingElementColors
    var currentRequestId by ElementSelectionState::currentRequestId
    var elementComposableName by ElementSelectionState::elementComposableName
    var elementAnalysisError by ElementSelectionState::elementAnalysisError

    var onSplitTokenSuccess by ElementSelectionState::onSplitTokenSuccess
    var showHardcodedDialog by ElementSelectionState::showHardcodedDialog
    var hardcodedColorPending by ElementSelectionState::hardcodedColorPending
    var hardcodedNewHex by ElementSelectionState::hardcodedNewHex
    var hardcodedUsageGlobal by ElementSelectionState::hardcodedUsageGlobal
    var hardcodedLocations by ElementSelectionState::hardcodedLocations
    var pendingRebuild by ElementSelectionState::pendingRebuild
    var lastGlobalEditInfo by ElementSelectionState::lastGlobalEditInfo
    var lastGlobalEditToken by ElementSelectionState::lastGlobalEditToken
    var lastGlobalEditColor by ElementSelectionState::lastGlobalEditColor
    var lastGlobalEditTime by ElementSelectionState::lastGlobalEditTime

    fun clearElementColors() = ElementSelectionState.clearElementColors()

    // ═══ Card in LazyColumn & Basic UI Props ═══
    var cardPadding: Dp by mutableStateOf(16.dp)
    var cardCornerRadius: Dp by mutableStateOf(12.dp)
    var cardBackgroundColor: Color by mutableStateOf(Color(0xFFFFFFFF))
    var userNameFontSize: TextUnit by mutableStateOf(18.sp)
    var userNameColor: Color by mutableStateOf(Color(0xFF000000))
    var titleText: String by mutableStateOf("Users")
    var titleFontSize: TextUnit by mutableStateOf(24.sp)
    var titleColor: Color by mutableStateOf(Color(0xFF000000))
    var columnPadding: Dp by mutableStateOf(0.dp)
    var spacerHeight: Dp by mutableStateOf(16.dp)

    // ═══ Theme Colors & Typography Extension Delegates ═══
    var onThemeColorUpdate: ((String, String) -> Boolean)? = null
    var onThemeColorReset: (() -> Unit)? = null
    var onTypographyUpdate: ((String, String, String) -> Boolean)? = null
    var onDimensionOverride: ((String, Float) -> Unit)? = null
    var onThemeTokensReceived: ((String) -> Unit)? = null
    var onElementAnalyzed: ((String) -> Unit)? = null
    var onEditDimensionAck: ((Boolean, String) -> Unit)? = null

    // ═══ Agent Status ═══
    private var _agentBusy by mutableStateOf(false)
    val agentBusy: Boolean get() = _agentBusy

    private var _queueCount by mutableStateOf(0)
    val queueCount: Int get() = _queueCount

    var lastQueueUpdate: Long by mutableStateOf(0L)
        private set

    fun setAgentBusy(busy: Boolean) {
        _agentBusy = busy
        lastQueueUpdate = System.currentTimeMillis()
        println("[BridgeState] 🤖 Agent busy: $busy")
    }

    fun setQueueCount(count: Int) {
        _queueCount = count
        lastQueueUpdate = System.currentTimeMillis()
        println("[BridgeState] 📥 Queue: $count edits")
    }

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

    // ═══ Baseline ═══
    private var baselineCaptured: Boolean = false
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
        println("[BridgeState] ♻️ Reverted to baseline (dimensions kept)")
    }

    // ═══ Track pending changes (not yet sent) ═══
    val pendingChanges = mutableStateMapOf<String, String>()

    fun hasPendingChanges(): Boolean = pendingChanges.isNotEmpty()

    fun markPending(property: String, value: String) {
        pendingChanges[property] = value
    }

    fun clearPending() {
        pendingChanges.clear()
    }

    // ═══ Utility ═══
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

    fun applyUpdate(property: String, value: String): Boolean {
        return try {
            when (property) {
                "cardPadding" -> {
                    cardPadding = value.toFloat().dp
                    true
                }
                "cardCornerRadius" -> {
                    cardCornerRadius = value.toFloat().dp
                    true
                }
                "cardBackgroundColor" -> {
                    cardBackgroundColor = parseColor(value)
                    true
                }
                "userNameFontSize" -> {
                    userNameFontSize = value.toFloat().sp
                    true
                }
                "userNameColor" -> {
                    userNameColor = parseColor(value)
                    true
                }
                "titleText" -> {
                    titleText = value
                    true
                }
                "titleFontSize" -> {
                    titleFontSize = value.toFloat().sp
                    true
                }
                "titleColor" -> {
                    titleColor = parseColor(value)
                    true
                }
                "columnPadding" -> {
                    columnPadding = value.toFloat().dp
                    true
                }
                "spacerHeight" -> {
                    spacerHeight = value.toFloat().dp
                    true
                }
                else -> {
                    if (property.startsWith("AppTypography.")) {
                        val parts = property.removePrefix("AppTypography.").split(".")
                        if (parts.size == 2) {
                            val styleKey = parts[0]
                            val propName = parts[1]
                            return onTypographyUpdate?.invoke(styleKey, propName, value) ?: false
                        }
                        return false
                    }
                    if (property.startsWith("AppColors.")) {
                        val key = property.removePrefix("AppColors.")
                        BridgeThemeRegistry.setColorHex(key, value)
                        return onThemeColorUpdate?.invoke(key, value) ?: true
                    }
                    false
                }
            }
        } catch (e: Exception) {
            println("[BridgeState] ❌ Failed to apply $property=$value: ${e.message}")
            false
        }
    }

    private fun parseColor(hex: String): Color {
        return com.composebridge.agent.util.ColorUtils.parseHexColor(hex)
    }
}
