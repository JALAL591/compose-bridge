package com.composebridge.agent

/**
 * Agent Python
 */
data class BridgeNode(
 val name: String?,
 val sourceFile: String?,
 val packageHash: Int?,
 val line: Int?,
 val utf16Offset: Int?,
 val utf16Length: Int?,
 val left: Int,
 val top: Int,
 val right: Int,
 val bottom: Int,
 val children: List<BridgeNode>
) {
 fun isUserNode(): Boolean {
 if (sourceFile == null) return false
 if (sourceFile.isBlank()) return false

 val blocked = listOf(
 "Box.kt", "Layout.kt", "Composables.kt", "Surface.kt",
 "Card.kt", "Text.kt", "Row.kt", "Column.kt", "Button.kt",
 "LazyLayout", "SubcomposeLayout", "MaterialTheme.kt",
 "ColorScheme.kt", "BasicText.kt", "LazyDsl.kt",
 "LazyListItemProvider.kt", "LazyLayoutItemContentFactory.kt",
 "LazyLayoutPinnableItem.kt", "SaveableStateHolder.kt",
 "LazySaveableStateHolder.kt", "Effects.kt", "CompositionLocal.kt",
 "CardDefaults", "Icon.kt", "TextField.kt", "Spacer.kt",
 "RememberSaveable.kt", "SnapshotState.kt", "Scrollable.kt",
 "SplineBasedFloatDecayAnimationSpec", "AndroidOverscroll",
 "LazyList.kt", "LazyListState.kt", "LazyListSemantics",
 "LazyListBeyondBounds", "DrawScope", "Modifier.kt"
 )

 return blocked.none { sourceFile.contains(it) }
 }

 /**
 * ( )
 */
 fun area(): Long {
 val w = (right - left).toLong()
 val h = (bottom - top).toLong()
 return w * h
 }

 /**
 * Is point (x,y) inside this element?
 */
 fun contains(x: Int, y: Int): Boolean {
 return x >= left && x <= right && y >= top && y <= bottom
 }

 /**
 * Collects all user nodes as flat list
 */
 fun collectUserNodes(): List<BridgeNode> {
 val result = mutableListOf<BridgeNode>()
 collectInto(result)
 return result
 }

 private fun collectInto(acc: MutableList<BridgeNode>) {
 if (isUserNode()) {
 acc.add(this)
 }
 children.forEach { it.collectInto(acc) }
 }

 /**
 * hierarchy 
 * If root is non-user, promote first user children
 */
 fun toFilteredTree(): BridgeNode? {
 if (isUserNode()) {
 return this.copy(children = children.mapNotNull { it.toFilteredTree() })
 } else {
 val userChildren = children.mapNotNull { it.toFilteredTree() }
 return when (userChildren.size) {
 0 -> null
 1 -> userChildren[0]
 else -> {
 // dummy container
 BridgeNode(
 name = "_group",
 sourceFile = null,
 packageHash = null,
 line = null,
 utf16Offset = null,
 utf16Length = null,
 left = userChildren.minOf { it.left },
 top = userChildren.minOf { it.top },
 right = userChildren.maxOf { it.right },
 bottom = userChildren.maxOf { it.bottom },
 children = userChildren
 )
 }
 }
 }
 }

 fun toJson(): String {
 val childrenJson = children.joinToString(",") { it.toJson() }
 return buildString {
 append("{")
 append("\"name\":${name.toJsonString()},")
 append("\"sourceFile\":${sourceFile.toJsonString()},")
 append("\"line\":${line ?: "null"},")
 append("\"utf16Offset\":${utf16Offset ?: "null"},")
 append("\"utf16Length\":${utf16Length ?: "null"},")
 append("\"bounds\":{")
 append("\"left\":$left,\"top\":$top,\"right\":$right,\"bottom\":$bottom")
 append("},")
 append("\"children\":[$childrenJson]")
 append("}")
 }
 }

 private fun String?.toJsonString(): String {
 if (this == null) return "null"
 return "\"${this.replace("\\", "\\\\").replace("\"", "\\\"")}\""
 }
}