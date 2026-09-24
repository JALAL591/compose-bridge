package com.composebridge.agent

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.geometry.Rect

/**
 * DesignModeRegistry — .
 *
 * - 
 * - 
 * - bounds 
 */
object DesignModeRegistry {

 /** */
 var isActive: Boolean by mutableStateOf(false)

 /** ( "cardPadding") */
 var selectedElement: String? by mutableStateOf(null)

 /** BridgeNode */
 var selectedSourceFile: String? by mutableStateOf(null)
 var selectedSourceLine: Int by mutableStateOf(0)

 /** Analyze Python */
 var analysisResult: String? by mutableStateOf(null)

 /** bounds */
 val elementBounds = mutableStateMapOf<String, Rect>()

 /** */
 fun registerBounds(name: String, bounds: Rect) {
 elementBounds[name] = bounds
 }

 /** */
 fun unregisterBounds(name: String) {
 elementBounds.remove(name)
 }

 /** / */
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

 /** */
 fun select(name: String?) {
 selectedElement = name
 }

 /** */
 fun reset() {
 isActive = false
 selectedElement = null
 selectedSourceFile = null
 selectedSourceLine = 0
 analysisResult = null
 elementBounds.clear()
 }
}