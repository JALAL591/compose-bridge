package com.composebridge.agent

import android.os.Handler
import android.os.Looper
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import java.util.concurrent.TimeUnit

class BridgeTransport(
 private val serverUrl: String,
 private val registry: CompositionRegistry
) {

 private val client = OkHttpClient.Builder()
 .pingInterval(20, TimeUnit.SECONDS)
 .build()

 private val mainHandler = Handler(Looper.getMainLooper())
 private val json = Json { ignoreUnknownKeys = true }

 @Volatile
 private var socket: WebSocket? = null

 fun connect() {
 val request = Request.Builder()
 .url(serverUrl)
 .build()

 println("[ComposeBridge] Connecting to $serverUrl")

 socket = client.newWebSocket(request, object : WebSocketListener() {

 override fun onOpen(webSocket: WebSocket, response: Response) {
 println("[ComposeBridge] ✅ Connected")
 webSocket.send("""{"type":"hello","agent":"composebridge","protocol":1}""")
 }

 override fun onMessage(webSocket: WebSocket, text: String) {
 println("[ComposeBridge] 📩 Received: $text")
 handleCommand(text) { reply ->
 webSocket.send(reply)
 }
 }

 override fun onMessage(webSocket: WebSocket, bytes: ByteString) {}

 override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
 println("[ComposeBridge] ❌ Failure: ${t.message}")
 socket = null
 }

 override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
 println("[ComposeBridge] Closed: $reason")
 socket = null
 }
 })
 }

 /**
 * WebSocket.
 */
 fun send(text: String): Boolean {
 val currentSocket = this.socket ?: return false
 return currentSocket.send(text)
 }

 private fun handleCommand(text: String, reply: (String) -> Unit) {
 mainHandler.post {
 try {
 println("[BridgeTransport] 📩 Received: ${text.take(200)}")

 // JSON ( )
 val obj = try {
 json.parseToJsonElement(text).jsonObject
 } catch (e: Exception) {
 println("[BridgeTransport] ❌ Invalid JSON: ${e.message}")
 return@post
 }

 val type = obj["type"]?.jsonPrimitive?.contentOrNull
 val action = obj["action"]?.jsonPrimitive?.contentOrNull

 println("[BridgeTransport] type=$type, action=$action")

 // ========================================
 // — 
 // ========================================
 if (type in listOf("hello_ack", "pong", "error", 
 "state_update_ack", "batch_update_ack", "reset_ack")) {
 println("[BridgeTransport] ℹ️ Informational: $type")
 return@post
 }

 // ========================================
 // 
 // ========================================
 when {
 action == "snapshot" -> {
 reply(captureSnapshot())
 }
 action == "ping" -> {
 reply("""{"type":"pong"}""")
 }
 }

 // ========================================
 // 
 // ========================================
 when (type) {
 "state_update" -> {
 val property = obj["property"]?.jsonPrimitive?.contentOrNull
 val value = obj["value"]?.jsonPrimitive?.contentOrNull
 if (property != null && value != null) {
 println("[BridgeTransport] 🔄 $property = $value")
 BridgeState.applyUpdate(property, value)
 } else {
 println("[BridgeTransport] ⚠️ Missing property/value")
 }
 }

 "batch_update" -> {
 println("[BridgeTransport] 🔄 Batch update")
 // updates array
 val updates = obj["updates"]
 if (updates != null) {
 // : applyUpdate
 val arr = updates.toString()
 val regex = Regex("""\{[^{}]*\}""")
 regex.findAll(arr).forEach { match ->
 val item = try {
 json.parseToJsonElement(match.value).jsonObject
 } catch (e: Exception) { null }
 
 val p = item?.get("property")?.jsonPrimitive?.contentOrNull
 val v = item?.get("value")?.jsonPrimitive?.contentOrNull
 if (p != null && v != null) {
 BridgeState.applyUpdate(p, v)
 }
 }
 }
 }

 "reset_state" -> {
 println("[BridgeTransport] ♻️ Reset applied")
 BridgeState.reset()
 }

 "theme_tokens_response" -> {
 // BridgeState 
 BridgeState.onThemeTokensReceived?.invoke(text)
 println("[BridgeTransport] 🎨 Theme tokens received")
 }

 "analyze_element_response" -> {
 println("[BridgeTransport] 📥 analyze_element_response received")
 val callback = BridgeState.onElementAnalyzed
 if (callback != null) {
 callback.invoke(text)
 println("[BridgeTransport] ✅ Callback invoked")
 } else {
 println("[BridgeTransport] ❌ No callback registered!")
 }
 }

 "toggle_design_mode" -> {
 DesignModeRegistry.toggle()
 println("[BridgeTransport] 🎯 Design Mode toggled from Python")
 }

 "edit_dimension" -> {
 val file = obj["file"]?.jsonPrimitive?.contentOrNull
 val line = obj["line"]?.jsonPrimitive?.intOrNull
 val newValue = obj["newValue"]?.jsonPrimitive?.contentOrNull

 if (file != null && line != null && newValue != null) {
 val dpValue = newValue.replace(".dp", "").toFloatOrNull()
 if (dpValue != null) {
 val key = "$file:$line:padding"
 BridgeState.onDimensionOverride?.invoke(key, dpValue)
 }
 }
 }

 "dimension_override" -> {
 val key = obj["key"]?.jsonPrimitive?.contentOrNull
 val value = obj["value"]?.jsonPrimitive?.contentOrNull
 if (key != null && value != null) {
 val dp = value.replace(".dp", "").toFloatOrNull()
 if (dp != null) {
 BridgeState.onDimensionOverride?.invoke(key, dp)
 println("[BridgeTransport] 📏 Override: $key = ${dp}.dp")
 }
 }
 }

 "dimension_reset" -> {
 BridgeState.onDimensionOverride?.invoke("__reset__", 0f)
 println("[BridgeTransport] ♻️ Dimension overrides cleared")
 }

 "edit_dimension_ack" -> {
 val fileUpdated = obj["file_updated"]
 val ok = fileUpdated?.jsonPrimitive?.contentOrNull == "true" || fileUpdated?.jsonPrimitive?.booleanOrNull == true
 val msg = obj["file_message"]?.jsonPrimitive?.contentOrNull ?: ""
 println("[BridgeTransport] ✅ edit_dimension_ack: $ok ($msg)")
 BridgeState.onEditDimensionAck?.invoke(ok, msg)
 }
 }
 } catch (e: Throwable) {
 println("[BridgeTransport] ❌ Handler error: ${e.message}")
 e.printStackTrace()
 }
 }
 }

 private fun captureSnapshot(): String {
 val tables = registry.snapshot()
 println("[ComposeBridge] 📸 Snapshot: ${tables.size} tables")

 val userTrees = mutableListOf<String>()

 tables.forEachIndexed { tableIdx, table ->
 val tree = table.toBridgeTree()
 if (tree != null) {
 val filteredTree = tree.toFilteredTree()
 if (filteredTree != null && filteredTree.isUserNode()) {
 val json = filteredTree.toJson()
 userTrees.add(json)
 BridgeDebugPrinter.printFilteredTree(filteredTree, 0, tableIdx)
 }
 }
 }

 val fullJson = """
 {"type":"snapshot","tableCount":${tables.size},"userTrees":${userTrees.size},"trees":[${userTrees.joinToString(",")}]}
 """.trimIndent()

 BridgeDebugPrinter.printJson(fullJson, "SNAPSHOT")

 return fullJson
 }

 fun close() {
 socket?.close(1000, "Agent shutdown")
 socket = null
 }
}