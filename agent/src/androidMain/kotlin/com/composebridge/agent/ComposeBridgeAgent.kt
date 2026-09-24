package com.composebridge.agent

import android.app.Activity
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.InternalComposeApi
import androidx.compose.runtime.currentComposer
import androidx.compose.runtime.tooling.LocalInspectionTables

@OptIn(InternalComposeApi::class)
object ComposeBridgeAgent {

 private val registry = CompositionRegistry()
 private var transport: BridgeTransport? = null

 @Composable
 fun Root(content: @Composable () -> Unit) {
 currentComposer.collectParameterInformation()
 registry.register(currentComposer.compositionData)
 CompositionLocalProvider(
 LocalInspectionTables provides registry.tables,
 content = content
 )
 }

 fun start(serverUrl: String = "ws://127.0.0.1:8711") {
 if (transport != null) return
 transport = BridgeTransport(serverUrl, registry)
 transport?.connect()
 }

 fun stop() {
 transport?.close()
 transport = null
 }

 /**
 * Overlay Activity ( onResume)
 */
 fun attachOverlay(activity: Activity) {
 BridgeOverlayManager.attach(activity)
 }

 fun detachOverlay() {
 BridgeOverlayManager.detach()
 }

 /**
 * / 
 */
 fun setSelectionMode(enabled: Boolean) {
 BridgeOverlayManager.setActive(enabled)
 }

 fun isSelectionMode(): Boolean = BridgeOverlayManager.isActive()

 /**
 * 
 */
 fun getAllUserNodes(): List<BridgeNode> {
 return registry.snapshot().flatMap { table ->
 table.toBridgeTree()?.collectUserNodes() ?: emptyList()
 }
 }

 /**
 * Python (WebSocket).
 * Python File.
 */
 fun sendStateUpdate(property: String, value: String): Boolean {
 val json = """
 {"type":"state_update","property":"$property","value":"$value"}
 """.trimIndent()
 return transport?.send(json) ?: false
 }

 /**
 * Python Theme Tokens.
 */
 fun requestThemeTokens(): Boolean {
 val json = """{"type":"theme_tokens"}"""
 return transport?.send(json) ?: false
 }

 /**
 * token.
 */
 fun sendColorUpdate(tokenKey: String, newHex: String): Boolean {
 val json = """
 {"type":"state_update","property":"$tokenKey","value":"$newHex"}
 """.trimIndent()
 return transport?.send(json) ?: false
 }

 /**
 * Analyze Python.
 */
 fun analyzeElement(
 file: String,
 line: Int,
 utf16Offset: Int = 0,
 utf16Length: Int = 0,
 ): Boolean {
 val json = """
 {"type":"analyze_element","file":"$file","line":$line,"offset":$utf16Offset,"length":$utf16Length}
 """.trimIndent()
 return transport?.send(json) ?: false
 }

 fun sendDimensionEdit(
 file: String,
 line: Int,
 offset: Int,
 length: Int,
 oldValue: String,
 newValue: String,
 ): Boolean {
 val json = """
 {"type":"edit_dimension","file":"$file","line":$line,"offset":$offset,"length":$length,"oldValue":"$oldValue","newValue":"$newValue"}
 """.trimIndent()
 return transport?.send(json) ?: false
 }

 /**
 * dimension_override Python — Registry.
 */
 fun sendDimensionOverride(tokenKey: String, value: String): Boolean {
 val json = """
 {"type":"dimension_override","key":"$tokenKey","value":"$value"}
 """.trimIndent()
 return transport?.send(json) ?: false
 }

 fun sendDimensionReset(): Boolean {
 val json = """{"type":"dimension_reset"}"""
 return transport?.send(json) ?: false
 }

 /**
 * Token BridgeSpacing.kt
 */
 fun sendTokenDefault(tokenName: String, value: String): Boolean {
 val json = """
 {"type":"update_token_default","token":"$tokenName","value":"$value"}
 """.trimIndent()
 return transport?.send(json) ?: false
 }

 /**
 * Analyze tree children.
 */
 fun analyzeElementWithTree(
 file: String,
 line: Int,
 utf16Offset: Int,
 utf16Length: Int,
 treeJson: String,
 ): Boolean {
 val escapedTree = treeJson.replace("\"", "\\\"")
 val json = """
 {"type":"analyze_element_with_tree","file":"$file","line":$line,"offset":$utf16Offset,"length":$utf16Length,"tree":"$escapedTree"}
 """.trimIndent()
 return transport?.send(json) ?: false
 }

 fun registry(): CompositionRegistry = registry
}