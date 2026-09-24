package com.composebridge.agent

/**
 * user 
 */
object BridgeHitTester {

 data class HitResult(
 val node: BridgeNode,
 val path: List<BridgeNode> // From root to element
 )

 /**
 * @param trees Current list from CompositionData
 * @param x Horizontal touch coordinate (in pixels)
 * @param y Vertical touch coordinate (in pixels)
 * @return user node null
 */
 fun hitTest(
 trees: List<BridgeNode>,
 x: Int,
 y: Int
 ): HitResult? {
 var best: BridgeNode? = null
 var bestArea = Long.MAX_VALUE
 var bestPath: List<BridgeNode> = emptyList()

 trees.forEach { tree ->
 walk(tree, x, y, emptyList()) { node, path ->
 if (node.isUserNode() && node.contains(x, y) && isProjectSource(node)) {
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

 return best?.let { HitResult(it, bestPath) }
 }

 /**
 * Is this source from project code?
 * 
 * ⚠️ File (Surface, Box, Text...) .
 * Keep only explicit internal files (Scaffold, NavigationDrawer).
 */
 private fun isProjectSource(node: BridgeNode): Boolean {
 val file = node.sourceFile ?: return false
 
 // Explicit internal Compose/Material files 
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
 
 // Accept any other .kt file
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

 /**
 * Formatted text result - printed in Logcat
 */
 fun formatResult(result: HitResult?): String {
 if (result == null) return "[HIT] No element at this point"

 val n = result.node
 n.sourceFile?.let { DesignModeRegistry.selectedSourceFile = it }
 n.line?.let { DesignModeRegistry.selectedSourceLine = it }

 return buildString {
 appendLine("[HIT] ========================================")
 appendLine("[HIT] 🎯 SELECTED ELEMENT")
 appendLine("[HIT] ========================================")
 appendLine("[HIT] Name: ${n.name ?: "?"}")
 appendLine("[HIT] Source: ${n.sourceFile}:${n.line}")
 appendLine("[HIT] UTF-16 off: ${n.utf16Offset}")
 appendLine("[HIT] UTF-16 len: ${n.utf16Length}")
 appendLine("[HIT] Bounds: (${n.left},${n.top})-(${n.right},${n.bottom})")
 appendLine("[HIT] Area: ${n.area()} px²")
 appendLine("[HIT] --- Path from root ---")
 result.path.forEachIndexed { i, p ->
 val indent = " ".repeat(i)
 appendLine("[HIT] $indent└─ ${p.name ?: "?"} @ ${p.sourceFile}:${p.line}")
 }
 appendLine("[HIT] --- JSON ---")
 appendLine("[HIT] ${n.toJson()}")
 appendLine("[HIT] ========================================")
 }
 }
}