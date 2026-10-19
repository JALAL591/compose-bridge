package com.composebridge.agent

import androidx.compose.runtime.tooling.CompositionData
import androidx.compose.ui.tooling.data.UiToolingDataApi
import androidx.compose.ui.tooling.data.mapTree

/**
 * Converts CompositionData into BridgeNode tree
 */
@OptIn(UiToolingDataApi::class)
fun CompositionData.toBridgeTree(): BridgeNode? {
    return try {
        mapTree(factory = { group, context, children ->
            val location = context.location
            val extractedText = try {
                group.data.filterIsInstance<String>().firstOrNull { it.isNotBlank() }
                    ?: group.data.filterIsInstance<CharSequence>().firstOrNull { it.isNotBlank() }?.toString()
            } catch (e: Throwable) {
                null
            }

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
                children = children.filterNotNull(),
                textContent = extractedText
            )
        })
    } catch (e: Throwable) {
        // If mapTree fails due to missing source info or any other error
        println("[ComposeBridge] toBridgeTree failed: ${e.message}")
        null
    }
}
