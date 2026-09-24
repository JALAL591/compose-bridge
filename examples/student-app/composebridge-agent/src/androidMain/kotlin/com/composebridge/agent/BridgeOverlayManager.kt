package com.composebridge.agent

import android.annotation.SuppressLint
import android.app.Activity
import android.view.ViewGroup

/**
 * BridgeOverlayManager — Overlay .
 *
 * :
 * - attach: BridgeSelectionOverlay ComposeView
 * - detach: 
 * - setActive: / 
 */
@SuppressLint("StaticFieldLeak")
object BridgeOverlayManager {

 private var overlay: BridgeSelectionOverlay? = null
 private var attachedActivity: Activity? = null

 /**
 * Attaches Overlay to Activity.
 * Activity .
 */
 fun attach(activity: Activity) {
 // ⚠️ === == — 
 if (overlay != null && attachedActivity === activity) return

 detach()

 // ⚠️ android.R.id.content — import android.R
 val root = activity.window.decorView.findViewById<ViewGroup>(
 android.R.id.content
 ) ?: return

 val newOverlay = BridgeSelectionOverlay(
 context = activity,
 getTrees = { getCurrentTrees() },
 onSelect = { result ->
 println(
 "[ComposeBridge] Selected: " +
 "${result?.node?.name} @ " +
 "${result?.node?.sourceFile}:${result?.node?.line}"
 )
 },
 )

 // ⭐ Disable Overlay
 newOverlay.onStopRequested = {
 println("[ComposeBridge] 🛑 Stop requested from overlay button")
 DesignModeRegistry.toggle()
 }

 root.addView(
 newOverlay,
 ViewGroup.LayoutParams(
 ViewGroup.LayoutParams.MATCH_PARENT,
 ViewGroup.LayoutParams.MATCH_PARENT,
 ),
 )

 // ⭐ ComposeView
 newOverlay.bringToFront()
 newOverlay.elevation = 100f

 overlay = newOverlay
 attachedActivity = activity

 println("[BridgeOverlayManager] ✅ Overlay attached")
 }

 /**
 * Overlay .
 */
 fun detach() {
 overlay?.let { view ->
 (view.parent as? ViewGroup)?.removeView(view)
 }
 overlay = null
 attachedActivity = null

 println("[BridgeOverlayManager] 🔌 Overlay detached")
 }

 /**
 * / .
 */
 fun setActive(active: Boolean) {
 overlay?.isActive = active
 println("[BridgeOverlayManager] Selection mode: ${if (active) "ON" else "OFF"}")
 }

 /**
 * Overlay 
 */
 fun isActive(): Boolean = overlay?.isActive == true

 /**
 * Composable .
 */
 private fun getCurrentTrees(): List<BridgeNode> {
 return ComposeBridgeAgent.registry().snapshot().mapNotNull { table ->
 table.toBridgeTree()?.toFilteredTree()
 }
 }
}