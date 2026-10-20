package com.composebridge.agent

import android.app.Activity
import android.content.Context

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
            // Visual containers known to have background, shape, border, elevation, dimensions
            val primaryVisualContainers = setOf("Surface", "Card", "AdaptiveActionCard", "Button")

            // 1. Search backwards from immediate parent for known primary visual containers or custom Card/Surface/Button
            val primaryParent = path.dropLast(1).reversed().firstOrNull { candidate ->
                val name = candidate.name ?: ""
                val matches = name in primaryVisualContainers ||
                    name.endsWith("Card") ||
                    name.endsWith("Surface") ||
                    name.endsWith("Button") ||
                    name.contains("Card")
                matches && (isProjectSource(candidate) || candidate.sourceFile != null)
            }
            if (primaryParent != null) return primaryParent

            // 2. Search backwards for Box or Container
            val secondaryVisualContainers = setOf("Box", "Container")
            val secondaryParent = path.dropLast(1).reversed().firstOrNull { candidate ->
                val name = candidate.name ?: ""
                val matches = name in secondaryVisualContainers || name.endsWith("Box") || name.endsWith("Container")
                matches && (isProjectSource(candidate) || candidate.sourceFile != null)
            }
            if (secondaryParent != null) return secondaryParent

            // 3. Skip layout-only containers (Column, Row, Spacer, Text, BasicText) and pick first non-layout project ancestor
            val nonVisualNames = setOf("Column", "Row", "Spacer", "Text", "BasicText")
            val nonLayoutAncestor = path.dropLast(1).reversed().firstOrNull { candidate ->
                isProjectSource(candidate) && (candidate.name ?: "") !in nonVisualNames
            }
            if (nonLayoutAncestor != null) return nonLayoutAncestor

            // 4. Fallback to any project ancestor
            return path.dropLast(1).reversed().firstOrNull { isProjectSource(it) }
                ?: path.dropLast(1).lastOrNull()
        }
    }

    /**
     * Checks if a node represents a Text composable.
     */
    fun isTextNode(node: BridgeNode): Boolean {
        val name = node.name ?: ""
        val file = node.sourceFile ?: ""
        val lowerFile = file.lowercase()
        return name == "Text" || name == "BasicText" || lowerFile.endsWith("text.kt") || lowerFile.endsWith("basictext.kt")
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
        mode: EditMode = BridgeState.currentEditMode,
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
                // TEXT Mode: Strictly match Text composables, but ascend to enclosing user project Composable!
                trees.forEach { tree ->
                    walk(tree, x, y, emptyList()) { node, path ->
                        if (node.contains(x, y) && isTextNode(node)) {
                            val a = node.area()
                            if (a in 1 until bestArea) {
                                val projectParent = (path + node).lastOrNull { isProjectSource(it) }
                                if (projectParent != null) {
                                    best = projectParent
                                    bestArea = a
                                    bestPath = path.takeWhile { it !== projectParent } + projectParent
                                }
                            }
                        }
                    }
                }

                // Smart Text fallback: If user clicked inside a Container that contains a Text child
                if (best == null) {
                    trees.forEach { tree ->
                        walk(tree, x, y, emptyList()) { node, path ->
                            if (node.contains(x, y) && isProjectSource(node)) {
                                val textChild = findFirstTextChild(node)
                                if (textChild != null) {
                                    val a = node.area()
                                    if (a in 1 until bestArea) {
                                        best = node // Select user project node, NEVER the internal Text.kt child
                                        bestArea = a
                                        bestPath = path + node
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        if (best == null) return null

        // Absolute guarantee: Never return a node from Android Compose internal library
        if (!isProjectSource(best!!)) {
            val projectAncestor = bestPath.lastOrNull { isProjectSource(it) }
            if (projectAncestor != null) {
                best = projectAncestor
                bestPath = bestPath.takeWhile { it !== projectAncestor } + projectAncestor
            } else {
                return null
            }
        }

        var textValue: String? = null
        var textRef: String? = null

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

            textRef = resolveTextReference(textValue, act)
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
    fun isProjectSource(node: BridgeNode): Boolean {
        val file = node.sourceFile ?: return false
        if (file.isBlank()) return false

        val lower = file.lowercase()
        val fileName = file.replace("\\", "/").substringAfterLast('/')
        // Reject any androidx, android internal libraries
        if (lower.contains("androidx.") || lower.contains("androidx/") || lower.contains("androidx\\")) return false
        if (lower.contains("android.") || lower.contains("android/") || lower.contains("android\\")) return false

        // Reject ComposeBridge agent internal UI files and components
        if (lower.contains("composebridge") || lower.contains("com.composebridge")) return false
        val agentInternalFiles = setOf(
            "DesignModeButton.kt",
            "GlobalPanels.kt",
            "BridgeSelectionOverlay.kt",
            "ComposeBridgeAgent.kt",
            "BridgeOverlayManager.kt",
            "BridgeHitTester.kt"
        )
        if (fileName in agentInternalFiles) return false
        val agentNodeNames = setOf("DesignModeButton", "GlobalPanels", "SmallFloatingActionButton", "FloatingActionButton")
        if (node.name in agentNodeNames) return false

        val internalFiles = setOf(
            "Text.kt",
            "BasicText.kt",
            "Scaffold.kt",
            "ScaffoldLayout.kt",
            "NavigationDrawer.kt",
            "Drawer.kt",
            "SubcomposeLayout.kt",
            "LazyColumn.kt",
            "LazyRow.kt",
            "MaterialTheme.kt",
            "ComposableLambda.kt",
            "VectorPainter.kt",
            "Box.kt",
            "Surface.kt",
            "Card.kt",
            "Row.kt",
            "Column.kt",
            "Button.kt",
            "Modifier.kt",
            "Layout.kt",
            "Composables.kt"
        )

        if (fileName in internalFiles) return false
        return fileName.endsWith(".kt")
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
            appendLine("[HIT] 🎯 SELECTED ELEMENT (${BridgeState.currentEditMode})")
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
                appendLine("[HIT] $indent└── ${p.name ?: "?"} @ ${p.sourceFile}:${p.line}")
            }
            appendLine("[HIT] ========================================")
        }
    }
    private fun findAppStringsClass(classLoader: ClassLoader, context: Any?): Class<*>? {
        // 1. Check system property override (configured by server/agent)
        val customClass = System.getProperty("composebridge.appstrings.class")
        if (!customClass.isNullOrBlank()) {
            try {
                return classLoader.loadClass(customClass)
            } catch (_: Throwable) {}
        }

        // 2. Discover package name dynamically from context if available
        val candidates = mutableListOf<String>()
        if (context != null) {
            try {
                val pkgName = when (context) {
                    is Context -> context.packageName
                    else -> {
                        val method = context.javaClass.methods.firstOrNull { it.name == "getPackageName" && it.parameterCount == 0 }
                        method?.invoke(context) as? String
                    }
                }
                if (!pkgName.isNullOrBlank()) {
                    candidates.add("$pkgName.ui.theme.AppStrings")
                    candidates.add("$pkgName.theme.AppStrings")
                    candidates.add("$pkgName.presentation.theme.AppStrings")
                }
            } catch (_: Throwable) {}
        }

        // 3. Fallbacks
        candidates.add("com.edu.teacher.ui.theme.AppStrings")

        for (className in candidates) {
            try {
                return classLoader.loadClass(className)
            } catch (_: Throwable) {}
        }
        return null
    }

    fun resolveTextReference(text: String?, context: Any? = null): String? {
        if (text.isNullOrBlank()) return null
        val target = text.trim()
        return try {
            val classLoader = context?.javaClass?.classLoader ?: Thread.currentThread().contextClassLoader
            val appStringsClass = findAppStringsClass(classLoader, context) ?: return null

            var bestSubMatch: String? = null
            var bestSubMatchLen = 0

            for (innerClass in appStringsClass.declaredClasses) {
                val groupName = innerClass.simpleName
                val instance = try {
                    innerClass.getField("INSTANCE").get(null)
                } catch (_: Throwable) { null }

                for (method in innerClass.declaredMethods) {
                    if (method.name.startsWith("get") && method.returnType == String::class.java) {
                        try {
                            val value = if (method.parameterCount == 0) {
                                method.invoke(instance) as? String
                            } else null
                            if (value != null) {
                                val vTrim = value.trim()
                                if (vTrim.isNotEmpty()) {
                                    val propName = method.name.removePrefix("get").replaceFirstChar { it.lowercase() }
                                    val fullKey = "AppStrings.$groupName.$propName"
                                    // Exact match
                                    if (vTrim == target) {
                                        return fullKey
                                    }
                                    // Template/substring match: e.g. target="Teacher ID: #123", vTrim="Teacher ID:"
                                    if (target.contains(vTrim) && vTrim.length > bestSubMatchLen && vTrim.length >= 3) {
                                        bestSubMatch = fullKey
                                        bestSubMatchLen = vTrim.length
                                    }
                                }
                            }
                        } catch (_: Throwable) {}
                    }
                }
            }
            bestSubMatch
        } catch (_: Throwable) {
            null
        }
    }
}
