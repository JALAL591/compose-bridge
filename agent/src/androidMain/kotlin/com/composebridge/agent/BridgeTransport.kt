/**
 * ComposeBridge Transport Coordinator.
 * منسق شبكة الاتصال الرئيسي لـ ComposeBridge الذي يدير عميل الـ WebSocket وتوجيه الرسائل واستقبال الـ APK.
 */
package com.composebridge.agent

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.compose.ui.unit.dp
import com.composebridge.agent.transport.AgentMessageDispatcher
import com.composebridge.agent.transport.ApkChunkReceiver
import com.composebridge.agent.transport.WebSocketClient
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

class BridgeTransport(
    @Volatile private var serverUrl: String = "ws://127.0.0.1:8711",
    private val registry: CompositionRegistry,
    @Volatile private var authToken: String = "",
    private val urlProvider: (() -> String)? = null,
    private val contextProvider: (() -> Context?)? = null,
) {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val json = Json { ignoreUnknownKeys = true }

    val apkReceiver = ApkChunkReceiver()
    val messageDispatcher = AgentMessageDispatcher(
        registry = registry,
        mainHandler = mainHandler,
        contextProvider = contextProvider,
        apkReceiver = apkReceiver,
    )
    val webSocketClient = WebSocketClient(
        serverUrl = serverUrl,
        authToken = authToken,
        urlProvider = urlProvider,
        contextProvider = contextProvider,
        mainHandler = mainHandler,
        messageDispatcher = messageDispatcher,
        apkReceiver = apkReceiver,
    )

    fun updateAuthToken(token: String) = webSocketClient.updateAuthToken(token)
    fun updateServerUrl(newUrl: String) = webSocketClient.updateServerUrl(newUrl)
    fun getServerUrl(): String = webSocketClient.getServerUrl()
    fun getAuthToken(): String = webSocketClient.getAuthToken()

    fun scheduleReconnect() = webSocketClient.scheduleReconnect()
    fun reconnect() = webSocketClient.reconnect()
    fun connect() = webSocketClient.connect()
    fun disconnect() = webSocketClient.disconnect()
    fun close() = webSocketClient.close()

    /**
     * Sends message over WebSocket with immediate local state pre-application.
     */
    fun send(text: String): Boolean {
        // ⭐ Apply locally before sending
        try {
            if (text.contains("state_update")) {
                val obj = json.parseToJsonElement(text).jsonObject
                val kind = obj["kind"]?.jsonPrimitive?.contentOrNull
                if (kind == "text") {
                    val token =
                        obj["token"]?.jsonPrimitive?.contentOrNull ?: obj["property"]?.jsonPrimitive?.contentOrNull
                    val value = obj["value"]?.jsonPrimitive?.contentOrNull
                    if (token != null && value != null) {
                        BridgeTextRegistry.setOverride(token, value)
                        println("[BridgeTransport] 📝 Local apply: $token = $value")
                    }
                } else if (kind == null || kind == "color" || kind == "split") {
                    val prop =
                        obj["property"]?.jsonPrimitive?.contentOrNull ?: obj["token"]?.jsonPrimitive?.contentOrNull
                    val value = obj["value"]?.jsonPrimitive?.contentOrNull
                    if (prop != null && value != null) {
                        val simpleKey = prop.removePrefix("AppColors.").trim()
                        BridgeThemeRegistry.setColorHex(simpleKey, value)
                        println("[BridgeTransport] 🎨 Local apply: $simpleKey = $value")
                    }
                }
            } else if (text.contains("update_token_default")) {
                val obj = json.parseToJsonElement(text).jsonObject
                val token = obj["token"]?.jsonPrimitive?.contentOrNull
                val value = obj["value"]?.jsonPrimitive?.contentOrNull
                if (token != null && value != null) {
                    val num = value.replace("dp", "").replace("sp", "").trim().toFloatOrNull()
                    if (num != null) {
                        BridgeDimensionRegistry.setOverride(token, num.dp)
                        println("[BridgeTransport] 📏 Local apply: $token = ${num}.dp")
                    }
                }
            }
        } catch (e: Exception) {
            println("[BridgeTransport] ⚠️ Local apply parse error: ${e.message}")
        }

        return webSocketClient.send(text)
    }
}
