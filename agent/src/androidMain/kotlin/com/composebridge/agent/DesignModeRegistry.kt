package com.composebridge.agent

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.geometry.Rect

/**
 * DesignModeRegistry — Central registry for design mode state.
 *
 * - Is design mode active?
 * - What element is currently selected?
 * - What are the bounds of each registered element?
 */
object DesignModeRegistry {

    /** Is design mode enabled? */
    var isActive: Boolean by mutableStateOf(false)

    /** Currently selected element (e.g. "cardPadding") */
    var selectedElement: String? by mutableStateOf(null)

    /** Selected element info from BridgeNode */
    var selectedSourceFile: String? by mutableStateOf(null)
    var selectedSourceLine: Int by mutableStateOf(0)

    /** Python bridge analysis result */
    var analysisResult: String? by mutableStateOf(null)

    /** Bounds of each registered element */
    val elementBounds = mutableStateMapOf<String, Rect>()

    /** Registers element with its position */
    fun registerBounds(name: String, bounds: Rect) {
        elementBounds[name] = bounds
    }

    /** Unregisters an element */
    fun unregisterBounds(name: String) {
        elementBounds.remove(name)
    }

    /** Toggles design mode */
    fun toggle() {
        if (isActive) {
            BridgeState.revertToBaseline()
            BridgeOverlayManager.setActive(false)
            println("[DesignModeRegistry] 🛑 Overlay deactivated")
        }
        isActive = !isActive
        if (isActive) {
            BridgeOverlayManager.setActive(true)
            println("[DesignModeRegistry] ✅ Overlay activated: ${BridgeOverlayManager.isActive()}")
        } else {
            selectedElement = null
            selectedSourceFile = null
            selectedSourceLine = 0
            analysisResult = null
        }
    }

    /** Selects an element */
    fun select(name: String?) {
        selectedElement = name
    }

    /** Resets registry */
    fun reset() {
        isActive = false
        selectedElement = null
        selectedSourceFile = null
        selectedSourceLine = 0
        analysisResult = null
        elementBounds.clear()
    }
}
