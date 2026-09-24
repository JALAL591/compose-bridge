package com.composebridge.agent

import androidx.compose.runtime.tooling.CompositionData
import androidx.compose.ui.tooling.data.UiToolingDataApi
import androidx.compose.ui.tooling.data.mapTree

/**
 * CompositionData BridgeNode tree
 */
@OptIn(UiToolingDataApi::class)
fun CompositionData.toBridgeTree(): BridgeNode? {
 return try {
 mapTree(factory = { _, context, children ->
 val location = context.location
 BridgeNode(
 name = context.name,
 sourceFile = location?.sourceFile,
 packageHash = location?.packageHash,
 line = location?.lineNumber,
 utf16Offset = location?.offset,
 utf16Length = location?.length,
 left = context.bounds.left,
 top = context.bounds.top,
 right = context.bounds.right,
 bottom = context.bounds.bottom,
 children = children.filterNotNull()
 )
 })
 } catch (e: Throwable) {
 // Failure mapTree source info Error 
 println("[ComposeBridge] toBridgeTree failed: ${e.message}")
 null
 }
}