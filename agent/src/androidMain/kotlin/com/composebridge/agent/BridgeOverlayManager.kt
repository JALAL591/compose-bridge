package com.composebridge.agent

import android.annotation.SuppressLint
import android.app.Activity
import android.view.ViewGroup

/**
 * BridgeOverlayManager — Manages the design overlay above the view hierarchy.
 *
 * Responsibilities:
 *  - attach: Adds BridgeSelectionOverlay above ComposeView
 *  - detach: Removes it
 *  - setActive: Toggles touch interception
 */
@SuppressLint("StaticFieldLeak")
object BridgeOverlayManager {

    private var overlay: BridgeSelectionOverlay? = null
    private var attachedActivity: Activity? = null

    /**
     * Attaches Overlay to the Activity.
     * If already attached to the same Activity, does nothing.
     */
    fun attach(activity: Activity) {
        // ⚠️ === rather than == — identity comparison
        if (overlay != null && attachedActivity === activity) return

        detach()

        // ⚠️ Use android.R.id.content directly — avoid importing android.R
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

        // ⭐ Close button inside Overlay
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

        // ⭐ Ensure it is above ComposeView
        newOverlay.bringToFront()
        newOverlay.elevation = 100f

        overlay = newOverlay
        attachedActivity = activity

        println("[BridgeOverlayManager] ✅ Overlay attached")
    }

    /**
     * Removes Overlay from view hierarchy.
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
     * Toggles touch interception.
     */
    fun setActive(active: Boolean) {
        overlay?.isActive = active
        println("[BridgeOverlayManager] Selection mode: ${if (active) "ON" else "OFF"}")
    }

    /**
     * Is Overlay currently active?
     */
    fun isActive(): Boolean = overlay?.isActive == true

    /**
     * Collects all current Composable slices.
     */
    private fun getCurrentTrees(): List<BridgeNode> {
        return ComposeBridgeAgent.registry().snapshot().mapNotNull { table ->
            table.toBridgeTree()?.toFilteredTree()
        }
    }
}