/**
 * ComposeBridge WebSocket Client.
 * إدارة جلسة الاتصال الفعلي مع خادم ComposeBridge عبر بروتوكول WebSocket.
 */
package com.composebridge.agent.transport

import android.content.Context
import android.os.Handler
import android.util.Log
import com.composebridge.agent.BridgeState
import okhttp3.*
import okio.ByteString
import java.util.concurrent.TimeUnit

class WebSocketClient(
    @Volatile private var serverUrl: String,
    @Volatile private var authToken: String = "",
    private val urlProvider: (() -> String)? = null,
    private val contextProvider: (() -> Context?)? = null,
    private val mainHandler: Handler,
    private val messageDispatcher: AgentMessageDispatcher,
    private val apkReceiver: ApkChunkReceiver,
) {
    companion object {
        private const val TAG = "ComposeBridge"
        private const val RECONNECT_DELAY_MS = 3000L
        private const val HEARTBEAT_INTERVAL_MS = 5000L
        private const val HEARTBEAT_TIMEOUT_MS = 60000L
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    @Volatile
    private var socket: WebSocket? = null

    @Volatile
    private var isClosedByUser = false

    @Volatile
    private var lastHeartbeatResponse = 0L

    @Volatile
    var isRemoteMode: Boolean = serverUrl.startsWith("wss://") || (!serverUrl.contains("127.0.0.1") && !serverUrl.contains("localhost"))

    private val reconnectRunnable = Runnable {
        if (!isClosedByUser) {
            val targetUrl = if (isRemoteMode && serverUrl.isNotBlank()) {
                serverUrl
            } else {
                urlProvider?.invoke()?.ifBlank { null } ?: serverUrl
            }
            this.serverUrl = targetUrl
            Log.d(TAG, "🔄 Auto-reconnect triggered: attempting to reconnect to $targetUrl...")
            connect()
        }
    }

    private val heartbeatRunnable = object : Runnable {
        override fun run() {
            val ws = socket
            if (ws != null && !isClosedByUser) {
                val now = System.currentTimeMillis()
                // During active APK build or chunk download, extend heartbeat grace period
                if (BridgeState.isBuildingApk) {
                    lastHeartbeatResponse = now
                }
                if (lastHeartbeatResponse > 0 && (now - lastHeartbeatResponse) > HEARTBEAT_TIMEOUT_MS) {
                    Log.w(TAG, "⚠️ Heartbeat timeout: no server response for >10s. Triggering reconnect...")
                    try {
                        ws.cancel()
                    } catch (_: Exception) {}
                    socket = null
                    scheduleReconnect()
                    return
                }

                val pingSent = ws.send("""{"type":"ping","t":$now}""")
                if (!pingSent) {
                    Log.w(TAG, "⚠️ Failed to send heartbeat ping. Triggering reconnect...")
                    try {
                        ws.cancel()
                    } catch (_: Exception) {}
                    socket = null
                    scheduleReconnect()
                    return
                }

                mainHandler.postDelayed(this, HEARTBEAT_INTERVAL_MS)
            }
        }
    }

    fun updateAuthToken(token: String) {
        this.authToken = token
    }

    fun updateServerUrl(newUrl: String) {
        if (newUrl.isNotBlank()) {
            Log.d(TAG, "🔄 Updating server URL to: $newUrl")
            this.serverUrl = newUrl
            this.isRemoteMode = newUrl.startsWith("wss://") || (!newUrl.contains("127.0.0.1") && !newUrl.contains("localhost"))
            reconnect()
        }
    }

    fun getServerUrl(): String = serverUrl
    fun getAuthToken(): String = authToken

    @Synchronized
    fun scheduleReconnect() {
        if (isClosedByUser) return
        mainHandler.post {
            BridgeState.isConnected = false
            BridgeState.isReconnecting = true
            BridgeState.connectionStatusText = "Reconnecting..."
        }
        mainHandler.removeCallbacks(reconnectRunnable)
        mainHandler.removeCallbacks(heartbeatRunnable)
        Log.d(TAG, "⏱️ Reconnection scheduled in 3s...")
        mainHandler.postDelayed(reconnectRunnable, RECONNECT_DELAY_MS)
    }

    fun reconnect() {
        Log.d(TAG, "🔄 Manual reconnect requested")
        isClosedByUser = false
        mainHandler.removeCallbacks(reconnectRunnable)
        connect()
    }

    @Synchronized
    fun connect() {
        if (socket != null) {
            try {
                socket?.close(1000, "Switching connection")
            } catch (_: Exception) {}
            socket = null
        }

        try {
            client.dispatcher.cancelAll()
        } catch (_: Exception) {}

        isClosedByUser = false
        mainHandler.removeCallbacks(reconnectRunnable)

        val targetUrl = if (isRemoteMode && serverUrl.isNotBlank()) {
            serverUrl
        } else {
            urlProvider?.invoke()?.ifBlank { null } ?: serverUrl
        }
        this.serverUrl = targetUrl

        val request = try {
            Request.Builder()
                .url(targetUrl)
                .build()
        } catch (e: Exception) {
            Log.e(TAG, "❌ Invalid server URL '$targetUrl': ${e.message}")
            mainHandler.post {
                BridgeState.connectionStatusText = "Invalid URL ($targetUrl)"
            }
            return
        }

        Log.d(TAG, "🔌 Connecting to $serverUrl...")
        mainHandler.post {
            BridgeState.isReconnecting = true
            BridgeState.connectionStatusText = "Connecting..."
        }

        socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                if (webSocket !== this@WebSocketClient.socket) {
                    try { webSocket.close(1000, "Stale socket") } catch (_: Exception) {}
                    return
                }
                Log.d(TAG, "✅ Connected to $serverUrl")
                lastHeartbeatResponse = System.currentTimeMillis()

                // Cancel any pending reconnect timers from previous sockets
                mainHandler.removeCallbacks(reconnectRunnable)

                mainHandler.post {
                    BridgeState.isConnected = true
                    BridgeState.isReconnecting = false
                    BridgeState.connectionStatusText = "Connected ($serverUrl)"
                }

                if (authToken.isNotEmpty()) {
                    Log.d(TAG, "🔐 Sending auth token...")
                    webSocket.send("""{"type":"auth","token":"$authToken"}""")
                } else {
                    webSocket.send("""{"type":"hello","agent":"composebridge","protocol":1}""")
                }

                // Start active heartbeat loop
                mainHandler.removeCallbacks(heartbeatRunnable)
                mainHandler.postDelayed(heartbeatRunnable, HEARTBEAT_INTERVAL_MS)

                apkReceiver.checkAndResumeApkDownload(webSocket, contextProvider?.invoke(), mainHandler)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                if (webSocket !== this@WebSocketClient.socket) return
                lastHeartbeatResponse = System.currentTimeMillis()
                if (text.contains("auth_ok")) {
                    Log.d(TAG, "🔓 Authentication confirmed by Bridge server!")
                    mainHandler.post {
                        BridgeState.connectionStatusText = "Connected ($serverUrl)"
                    }
                    return
                }
                if (text.contains("UNAUTHORIZED")) {
                    Log.e(TAG, "❌ Authentication failed: Invalid token")
                    mainHandler.post {
                        BridgeState.connectionStatusText = "Auth Failed (Invalid Token)"
                    }
                    return
                }
                messageDispatcher.dispatch(text) { reply ->
                    webSocket.send(reply)
                }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                if (webSocket !== this@WebSocketClient.socket) return
                lastHeartbeatResponse = System.currentTimeMillis()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (webSocket !== this@WebSocketClient.socket) {
                    Log.d(TAG, "Ignoring onFailure from stale socket: ${t.message}")
                    return
                }
                Log.w(TAG, "❌ Failure: ${t.message}")
                socket = null
                if (!isClosedByUser) {
                    scheduleReconnect()
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (webSocket !== this@WebSocketClient.socket) {
                    Log.d(TAG, "Ignoring onClosed from stale socket (code=$code)")
                    return
                }
                Log.d(TAG, "🔌 Closed: $reason (code=$code)")
                socket = null
                if (code == 4001) {
                    Log.e(TAG, "❌ Server rejected connection: Unauthorized (code 4001). Reconnect stopped until new token is set.")
                    mainHandler.removeCallbacks(reconnectRunnable)
                    mainHandler.post {
                        BridgeState.isConnected = false
                        BridgeState.isReconnecting = false
                        BridgeState.connectionStatusText = "Unauthorized (Invalid Token)"
                    }
                    return
                } else if (code == 4029) {
                    Log.e(TAG, "❌ Server rejected connection: Rate limit exceeded (code 4029)")
                    mainHandler.post {
                        BridgeState.connectionStatusText = "Rate Limited (Wait 1m)"
                    }
                }
                if (!isClosedByUser) {
                    scheduleReconnect()
                }
            }
        })
    }

    /**
     * Sends message over WebSocket.
     */
    fun send(text: String): Boolean {
        val currentSocket = this.socket
        if (currentSocket == null) {
            Log.e(TAG, "❌ [BridgeTransport.send] Cannot send message: socket is NULL! (serverUrl=$serverUrl)")
            return false
        }
        Log.d(TAG, "🚀 [BridgeTransport.send] Sending text via WebSocket: $text")
        val sent = currentSocket.send(text)
        Log.d(TAG, "📤 [BridgeTransport.send] WebSocket.send returned: $sent")
        return sent
    }

    fun disconnect() {
        Log.d(TAG, "🔌 Disconnecting active WebSocket session")
        isClosedByUser = true
        mainHandler.removeCallbacks(reconnectRunnable)
        mainHandler.removeCallbacks(heartbeatRunnable)
        try {
            socket?.close(1000, "Disconnecting")
        } catch (_: Exception) {}
        socket = null
        try {
            client.dispatcher.cancelAll()
        } catch (_: Exception) {}
        mainHandler.post {
            BridgeState.isConnected = false
            BridgeState.isReconnecting = false
            BridgeState.connectionStatusText = "Disconnected"
        }
    }

    fun close() {
        Log.d(TAG, "🛑 Closing BridgeTransport")
        isClosedByUser = true
        mainHandler.removeCallbacks(reconnectRunnable)
        mainHandler.removeCallbacks(heartbeatRunnable)
        try {
            socket?.close(1000, "Agent shutdown")
        } catch (_: Exception) {}
        socket = null
        mainHandler.post {
            BridgeState.isConnected = false
            BridgeState.isReconnecting = false
            BridgeState.connectionStatusText = "Disconnected ($serverUrl)"
        }
    }
}
