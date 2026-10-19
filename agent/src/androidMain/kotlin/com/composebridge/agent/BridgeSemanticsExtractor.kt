package com.composebridge.agent

import android.app.Activity
import android.view.View
import android.view.ViewGroup
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsOwner
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull

/**
 * BridgeSemanticsExtractor
 *
 * Extracts runtime evaluated text and properties directly from Compose Semantics tree.
 * Does NOT rely on source code AST regex — inspects actual rendered text on screen.
 */
object BridgeSemanticsExtractor {

    data class SemanticsTextResult(
        val text: String,
        val boundsLeft: Float,
        val boundsTop: Float,
        val boundsRight: Float,
        val boundsBottom: Float,
    )

    /**
     * Finds the actual runtime text displayed at the given screen coordinates (x, y)
     * using Compose SemanticsProperties.Text or SemanticsProperties.EditableText.
     *
     * @param activity The host Activity
     * @param x Touch X coordinate in window/screen pixels
     * @param y Touch Y coordinate in window/screen pixels
     * @return Evaluated String displayed on screen, or null
     */
    fun findTextAt(activity: Activity?, x: Float, y: Float): String? {
        val result = findSemanticsTextResultAt(activity, x, y)
        return result?.text
    }

    /**
     * Finds detailed SemanticsTextResult containing the evaluated text and bounds.
     */
    fun findSemanticsTextResultAt(activity: Activity?, x: Float, y: Float): SemanticsTextResult? {
        val act = activity ?: return null
        val composeViews = findComposeViews(act.window.decorView)

        var bestResult: SemanticsTextResult? = null
        var bestArea = Float.MAX_VALUE

        for (cv in composeViews) {
            val owner = getSemanticsOwner(cv) ?: continue
            val root = try {
                owner.unmergedRootSemanticsNode
            } catch (e: Throwable) {
                try {
                    owner.rootSemanticsNode
                } catch (e2: Throwable) {
                    null
                }
            } ?: continue

            walkSemantics(root) { node ->
                val bounds = try {
                    node.boundsInWindow
                } catch (e: Throwable) {
                    null
                }

                if (bounds != null && bounds.contains(Offset(x, y))) {
                    val texts = try {
                        node.config.getOrNull(SemanticsProperties.Text)
                    } catch (e: Throwable) {
                        null
                    }

                    val editable = try {
                        node.config.getOrNull(SemanticsProperties.EditableText)
                    } catch (e: Throwable) {
                        null
                    }

                    val extracted = when {
                        !texts.isNullOrEmpty() -> texts.joinToString("") { it.text }
                        editable != null -> editable.text
                        else -> null
                    }

                    if (!extracted.isNullOrBlank()) {
                        val area = bounds.width * bounds.height
                        if (area < bestArea) {
                            bestArea = area
                            bestResult = SemanticsTextResult(
                                text = extracted,
                                boundsLeft = bounds.left,
                                boundsTop = bounds.top,
                                boundsRight = bounds.right,
                                boundsBottom = bounds.bottom,
                            )
                        }
                    }
                }
            }
        }
        return bestResult
    }

    private fun walkSemantics(node: SemanticsNode, action: (SemanticsNode) -> Unit) {
        action(node)
        val children = try {
            node.children
        } catch (e: Throwable) {
            emptyList()
        }
        children.forEach { walkSemantics(it, action) }
    }

    private fun findComposeViews(view: View): List<View> {
        val list = mutableListOf<View>()
        val className = view::class.java.name
        if (className.contains("AndroidComposeView") || className.contains("ComposeView")) {
            list.add(view)
        }
        if (view is ViewGroup) {
            for (i in 0 until view.childCount) {
                list.addAll(findComposeViews(view.getChildAt(i)))
            }
        }
        return list
    }

    private fun getSemanticsOwner(view: View): SemanticsOwner? {
        return try {
            val method = view::class.java.getMethod("getSemanticsOwner")
            method.isAccessible = true
            method.invoke(view) as? SemanticsOwner
        } catch (e: Throwable) {
            try {
                val field = view::class.java.getDeclaredField("semanticsOwner")
                field.isAccessible = true
                field.get(view) as? SemanticsOwner
            } catch (e2: Throwable) {
                null
            }
        }
    }
}
