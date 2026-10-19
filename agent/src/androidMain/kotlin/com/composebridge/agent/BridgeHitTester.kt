package com.composebridge.agent

import android.app.Activity

/**
 * Finds the targeted user element containing the touch point based on current EditMode.
 */
object BridgeHitTester {

    data class HitResult(
        val node: BridgeNode,
        val path: List<BridgeNode>,
        val textValue: String? = null,
        val textReference: String? = null
    ) {
        fun findParentContainer(): BridgeNode? {
            return path.dropLast(1).lastOrNull { it.isUserNode() && isProjectSource(it) && !isTextNode(it) }
                ?: path.dropLast(1).lastOrNull { !isTextNode(it) }
                ?: path.dropLast(1).lastOrNull()
        }
    }

    /**
     * Checks if a node represents a Text composable.
     */
    fun isTextNode(node: BridgeNode): Boolean {
        val name = node.name ?: ""
        val file = node.sourceFile ?: ""
        return name == "Text" || name == "BasicText" || file.contains("Text.kt")
    }

    /**
     * @param trees Current list of CompositionData
     * @param x Horizontal touch coordinate (in pixels)
     * @param y Vertical touch coordinate (in pixels)
     * @param mode Current active EditMode
     * @param activity Host Activity for Semantics inspection
     * @return Target node containing the point, or null
     */
    fun hitTest(
        trees: List<BridgeNode>,
        x: Int,
        y: Int,
        mode: EditMode = BridgeState.currentMode,
        activity: Activity? = null
    ): HitResult? {
        var best: BridgeNode? = null
        var bestArea = Long.MAX_VALUE
        var bestPath: List<BridgeNode> = emptyList()

        when (mode) {
            EditMode.COLOR -> {
                // COLOR Mode: Ignore Text nodes and select enclosing container
                trees.forEach { tree ->
                    walk(tree, x, y, emptyList()) { node, path ->
                        if (node.isUserNode() && node.contains(x, y) && isProjectSource(node) && !isTextNode(node)) {
                            val a = node.area()
                            val depth = path.size
                            val currentBestDepth = bestPath.size

                            val isDeeper = depth > currentBestDepth
                            val isSameAreaDeeper = (a == bestArea && isDeeper)
                            val isSmallerArea = (a in 1 until bestArea)

                            if (isSmallerArea || isSameAreaDeeper) {
                                best = node
                                bestArea = a
                                bestPath = path + node
                            }
                        }
                    }
                }

                // Fallback: If tap landed only in Text bounds, ascend to parent container
                if (best == null) {
                    trees.forEach { tree ->
                        walk(tree, x, y, emptyList()) { node, path ->
                            if (node.isUserNode() && node.contains(x, y) && isProjectSource(node)) {
                                val parent = path.lastOrNull { !isTextNode(it) && isProjectSource(it) }
                                if (parent != null) {
                                    val a = parent.area()
                                    if (a in 1 until bestArea) {
                                        best = parent
                                        bestArea = a
                                        bestPath = path.takeWhile { it !== parent } + parent
                                    }
                                }
                            }
                        }
                    }
                }
            }

            EditMode.DIMENSION -> {
                // DIMENSION Mode: Focus on containers & layout elements, ignore pure Text leaves
                trees.forEach { tree ->
                    walk(tree, x, y, emptyList()) { node, path ->
                        if (node.isUserNode() && node.contains(x, y) && isProjectSource(node) && !isTextNode(node)) {
                            val a = node.area()
                            val depth = path.size
                            val currentBestDepth = bestPath.size

                            val isDeeper = depth > currentBestDepth
                            val isSameAreaDeeper = (a == bestArea && isDeeper)
                            val isSmallerArea = (a in 1 until bestArea)

                            if (isSmallerArea || isSameAreaDeeper) {
                                best = node
                                bestArea = a
                                bestPath = path + node
                            }
                        }
                    }
                }

                if (best == null) {
                    trees.forEach { tree ->
                        walk(tree, x, y, emptyList()) { node, path ->
                            if (node.isUserNode() && node.contains(x, y) && isProjectSource(node)) {
                                val parent = path.lastOrNull { !isTextNode(it) && isProjectSource(it) } ?: node
                                val a = parent.area()
                                if (a in 1 until bestArea) {
                                    best = parent
                                    bestArea = a
                                    bestPath = path
                                }
                            }
                        }
                    }
                }
            }

            EditMode.TEXT -> {
                // TEXT Mode: Strictly match Text composables only
                trees.forEach { tree ->
                    walk(tree, x, y, emptyList()) { node, path ->
                        if (node.isUserNode() && node.contains(x, y) && isProjectSource(node) && isTextNode(node)) {
                            val a = node.area()
                            if (a in 1 until bestArea) {
                                best = node
                                bestArea = a
                                bestPath = path + node
                            }
                        }
                    }
                }

                // Smart Text fallback: If user clicked inside a Button / Card / Container that contains a Text child
                if (best == null) {
                    trees.forEach { tree ->
                        walk(tree, x, y, emptyList()) { node, path ->
                            if (node.isUserNode() && node.contains(x, y) && isProjectSource(node)) {
                                val textChild = findFirstTextChild(node)
                                if (textChild != null) {
                                    val a = node.area()
                                    if (a in 1 until bestArea) {
                                        best = textChild
                                        bestArea = a
                                        bestPath = path + node + textChild
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        if (best == null) return null

        var textValue: String? = null
        val textRef: String? = null

        if (mode == EditMode.TEXT) {
            val act = activity ?: BridgeOverlayManager.attachedActivity
            // 1. Try finding at exact touch coordinates
            textValue = BridgeSemanticsExtractor.findTextAt(act, x.toFloat(), y.toFloat())

            // 2. If null, try center of the resolved node bounds
            if (textValue == null && best != null) {
                val cx = ((best!!.left + best!!.right) / 2).toFloat()
                val cy = ((best!!.top + best!!.bottom) / 2).toFloat()
                textValue = BridgeSemanticsExtractor.findTextAt(act, cx, cy)
            }
        }

        return HitResult(best!!, bestPath, textValue = textValue, textReference = textRef)
    }

    private fun findFirstTextChild(node: BridgeNode): BridgeNode? {
        if (isTextNode(node)) return node
        for (child in node.children) {
            val found = findFirstTextChild(child)
            if (found != null) return found
        }
        return null
    }

    /**
     * Is this source from the project code?
     */
    private fun isProjectSource(node: BridgeNode): Boolean {
        val file = node.sourceFile ?: return false

        val internalFiles = setOf(
            "Scaffold.kt",
            "ScaffoldLayout.kt",
            "NavigationDrawer.kt",
            "Drawer.kt",
            "SubcomposeLayout.kt",
            "LazyColumn.kt",
            "LazyRow.kt",
            "MaterialTheme.kt",
            "ComposableLambda.kt",
            "VectorPainter.kt"
        )

        if (file in internalFiles) return false
        return file.endsWith(".kt")
    }

    private fun walk(
        node: BridgeNode,
        x: Int,
        y: Int,
        currentPath: List<BridgeNode>,
        action: (BridgeNode, List<BridgeNode>) -> Unit
    ) {
        action(node, currentPath)
        val newPath = currentPath + node
        node.children.forEach { walk(it, x, y, newPath, action) }
    }

    fun formatResult(result: HitResult?): String {
        if (result == null) return "[HIT] No element at this point"

        val n = result.node
        n.sourceFile?.let { DesignModeRegistry.selectedSourceFile = it }
        n.line?.let { DesignModeRegistry.selectedSourceLine = it }

        return buildString {
            appendLine("[HIT] ========================================")
            appendLine("[HIT] 🎯 SELECTED ELEMENT (${BridgeState.currentMode})")
            appendLine("[HIT] ========================================")
            appendLine("[HIT] Name:        ${n.name ?: "?"}")
            appendLine("[HIT] Source:      ${n.sourceFile}:${n.line}")
            appendLine("[HIT] UTF-16 off:  ${n.utf16Offset}")
            appendLine("[HIT] UTF-16 len:  ${n.utf16Length}")
            appendLine("[HIT] Bounds:      (${n.left},${n.top})-(${n.right},${n.bottom})")
            appendLine("[HIT] Area:        ${n.area()} px²")
            if (result.textValue != null) {
                appendLine("[HIT] Text Value:  ${result.textValue}")
            }
            if (result.textReference != null) {
                appendLine("[HIT] Text Ref:    ${result.textReference}")
            }
            appendLine("[HIT] --- Path from root ---")
            result.path.forEachIndexed { i, p ->
                val indent = "  ".repeat(i)
                appendLine("[HIT] $indent└─ ${p.name ?: "?"} @ ${p.sourceFile}:${p.line}")
            }
            appendLine("[HIT] ========================================")
        }
    }
}
