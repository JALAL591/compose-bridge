/**
 * ComposeBridge Element Selection State.
 * إدارة حالة العنصر المحدد وخصائصه وألوانه ونصوصه وأبعاده في وضع الفحص والتركيز.
 */
package com.composebridge.agent.state

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.composebridge.agent.ElementColorInfo
import com.composebridge.agent.ElementColorLocation
import com.composebridge.agent.ElementDimensionInfo
import com.composebridge.agent.ElementTextInfo

object ElementSelectionState {
    val elementColors = mutableStateListOf<ElementColorInfo>()
    val elementDimensions = mutableStateListOf<ElementDimensionInfo>()
    val elementTexts = mutableStateListOf<ElementTextInfo>()
    var lastEvaluatedScreenText: String? by mutableStateOf(null)
    var showDimensionDialog: Boolean by mutableStateOf(false)
    var dimensionPending: ElementDimensionInfo? by mutableStateOf(null)
    var dimensionNewValue: Float? by mutableStateOf(null)
    var isLoadingElementColors: Boolean by mutableStateOf(false)
    var currentRequestId: Long by mutableStateOf(0L)
    var elementComposableName: String by mutableStateOf("Element")
    var elementAnalysisError: String? by mutableStateOf(null)

    var onSplitTokenSuccess: ((String) -> Unit)? = null

    // Hardcoded dialog state
    var showHardcodedDialog: Boolean by mutableStateOf(false)
    var hardcodedColorPending: ElementColorInfo? by mutableStateOf(null)
    var hardcodedNewHex: String? by mutableStateOf(null)

    // Hardcoded info
    var hardcodedUsageGlobal: Int by mutableStateOf(0)
    var hardcodedLocations: List<ElementColorLocation> by mutableStateOf(emptyList())

    // Rebuild Status
    var pendingRebuild: Boolean by mutableStateOf(false)
    var lastGlobalEditInfo: String? by mutableStateOf(null)

    // Global Edit Anti-Bounce
    var lastGlobalEditToken: String? = null
    var lastGlobalEditColor: String? = null
    var lastGlobalEditTime: Long = 0L

    fun clearElementColors() {
        elementColors.clear()
        elementDimensions.clear()
        elementTexts.clear()
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
}

