package com.composebridge.agent

import android.os.Handler
import android.os.Looper
import android.util.Log
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import androidx.compose.ui.unit.dp
import java.util.concurrent.TimeUnit

class BridgeTransport(
    private val serverUrl: String,
    private val registry: CompositionRegistry,
    private val authToken: String = "test-token-local-dev",
) {

    private val client = OkHttpClient.Builder()
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    private val mainHandler = Handler(Looper.getMainLooper())
    private val json = Json { ignoreUnknownKeys = true }

    @Volatile
    private var socket: WebSocket? = null

    private val TAG = "ComposeBridge"
    private val RECONNECT_DELAY_MS = 3000L
    private val HEARTBEAT_INTERVAL_MS = 5000L
    private val HEARTBEAT_TIMEOUT_MS = 10000L

    @Volatile
    private var isClosedByUser = false

    @Volatile
    private var lastHeartbeatResponse = 0L

    private val reconnectRunnable = Runnable {
        if (!isClosedByUser) {
            Log.d(TAG, "🔄 Auto-reconnect triggered: attempting to reconnect to $serverUrl...")
            connect()
        }
    }

    private val heartbeatRunnable = object : Runnable {
        override fun run() {
            val ws = socket
            if (ws != null && !isClosedByUser) {
                val now = System.currentTimeMillis()
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
                socket?.cancel()
            } catch (_: Exception) {}
            socket = null
        }

        isClosedByUser = false
        mainHandler.removeCallbacks(reconnectRunnable)

        val request = Request.Builder()
            .url(serverUrl)
            .build()

        Log.d(TAG, "🔌 Connecting to $serverUrl...")
        mainHandler.post {
            BridgeState.isReconnecting = true
            BridgeState.connectionStatusText = "Connecting..."
        }

        socket = client.newWebSocket(request, object : WebSocketListener() {

            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d(TAG, "✅ Connected to $serverUrl")
                lastHeartbeatResponse = System.currentTimeMillis()

                mainHandler.post {
                    BridgeState.isConnected = true
                    BridgeState.isReconnecting = false
                    BridgeState.connectionStatusText = "Connected"
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
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                lastHeartbeatResponse = System.currentTimeMillis()
                handleCommand(text) { reply ->
                    webSocket.send(reply)
                }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                lastHeartbeatResponse = System.currentTimeMillis()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "❌ Failure: ${t.message}")
                socket = null
                scheduleReconnect()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.d(TAG, "🔌 Closed: $reason (code=$code)")
                socket = null
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
        // ⭐ Apply locally before sending
        try {
            if (text.contains("state_update")) {
                val obj = json.parseToJsonElement(text).jsonObject
                val kind = obj["kind"]?.jsonPrimitive?.contentOrNull
                if (kind == "text") {
                    val token = obj["token"]?.jsonPrimitive?.contentOrNull ?: obj["property"]?.jsonPrimitive?.contentOrNull
                    val value = obj["value"]?.jsonPrimitive?.contentOrNull
                    if (token != null && value != null) {
                        BridgeTextRegistry.setOverride(token, value)
                        println("[BridgeTransport] 📝 Local apply: $token = $value")
                    }
                } else if (kind == null || kind == "color" || kind == "split") {
                    val prop = obj["property"]?.jsonPrimitive?.contentOrNull ?: obj["token"]?.jsonPrimitive?.contentOrNull
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

        val currentSocket = this.socket ?: return false
        return currentSocket.send(text)
    }

    private fun handleCommand(text: String, reply: (String) -> Unit) {
        mainHandler.post {
            try {
                println("[BridgeTransport] 📩 Received: ${text.take(200)}")

                // Parse JSON robustly
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
                // Informational messages — no response required
                // ========================================
                if (type in listOf("hello_ack", "pong", "error", 
                                   "batch_update_ack", "reset_ack", "mcp_state_update_ack")) {
                    println("[BridgeTransport] ℹ️ Informational: $type")
                    return@post
                }

                // ========================================
                // Messages requiring response
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
                // State update messages
                // ========================================
                when (type) {
                    "auth_ok" -> {
                        println("[ComposeBridge] ✅ Authenticated")
                        reply("""{"type":"hello","agent":"composebridge","protocol":1}""")
                    }

                    "mcp_state_update" -> {
                        val property = obj["property"]?.jsonPrimitive?.contentOrNull
                        val value = obj["value"]?.jsonPrimitive?.contentOrNull
                        if (property != null && value != null) {
                            println("[BridgeTransport] 🤖 MCP Update: $property = $value")
                            
                            // ⭐ Detect semantic type
                            val key = property.removePrefix("AppColors.").trim()
                            val isNumeric = value.all { it.isDigit() || it == '.' } && value.isNotEmpty()
                            val isColor = value.startsWith("#") || value.startsWith("0x") || value.startsWith("0X")
                            
                            when {
                                isNumeric -> {
                                    // Dimension (e.g., welcomeCardHeight = 500)
                                    val dpValue = value.toFloatOrNull()
                                    if (dpValue != null) {
                                        println("[BridgeTransport] 📏 Dimension: $key = ${dpValue}.dp")
                                        BridgeState.onDimensionOverride?.invoke(key, dpValue)
                                    } else {
                                        println("[BridgeTransport] ⚠️ Cannot parse dimension: $value")
                                    }
                                }
                                
                                isColor -> {
                                    // Color (e.g., Primary = #EF4444)
                                    println("[BridgeTransport] 🎨 Color: $key = $value")
                                    BridgeState.applyUpdate(property, value)
                                }
                                
                                else -> {
                                    // Fallback — treat as color update
                                    println("[BridgeTransport] ⚠️ Unknown type: $value")
                                    BridgeState.applyUpdate(property, value)
                                }
                            }
                        } else {
                            println("[BridgeTransport] ⚠️ Missing property/value in mcp_state_update")
                        }
                    }

                    "state_update" -> {
                        val kind = obj["kind"]?.jsonPrimitive?.contentOrNull
                        val token = obj["token"]?.jsonPrimitive?.contentOrNull
                        val property = obj["property"]?.jsonPrimitive?.contentOrNull
                        val rawValue = obj["value"]?.jsonPrimitive?.contentOrNull

                        if (kind == "dimension") {
                            val numVal = rawValue?.removeSuffix(".dp")?.removeSuffix(".sp")?.toFloatOrNull()
                            if (!token.isNullOrEmpty() && numVal != null) {
                                BridgeDimensionRegistry.setOverride(token, numVal.dp)
                                println("[BridgeTransport] 📏 dimension state_update: $token = $numVal.dp")
                            }
                        } else if (kind == "text") {
                            val tokenName = token ?: property ?: ""
                            if (tokenName.isNotEmpty() && rawValue != null) {
                                BridgeTextRegistry.setOverride(tokenName, rawValue)
                                android.util.Log.i("BridgeTransport", "📝 text state_update: $tokenName = '$rawValue'")
                                println("[BridgeTransport] 📝 text state_update: $tokenName = '$rawValue'")
                            }
                        } else {
                            val tokenName = token ?: property?.removePrefix("AppColors.")?.trim()
                            val value = if (rawValue != null && rawValue.contains("0x", ignoreCase = true)) {
                                val match = Regex("""0x[0-9A-Fa-f]+""").find(rawValue)
                                match?.value ?: rawValue
                            } else rawValue

                            if (!tokenName.isNullOrEmpty() && !value.isNullOrEmpty()) {
                                val cleanHex = value
                                    .removePrefix("#")
                                    .removePrefix("0x")
                                    .removePrefix("0X")
                                    .uppercase()
                                
                                BridgeThemeRegistry.setColorHex(tokenName, cleanHex)
                                android.util.Log.i("BridgeTransport", "🎨 state_update: $tokenName = $cleanHex")
                                println("[BridgeTransport] 🎨 state_update: $tokenName = $cleanHex")
                                
                                val fullProperty = if (tokenName.startsWith("AppColors.")) tokenName else "AppColors.$tokenName"
                                BridgeState.applyUpdate(fullProperty, cleanHex)
                            } else {
                                println("[BridgeTransport] ⚠️ Missing token/value in state_update: token=$token, prop=$property, val=$rawValue")
                            }
                        }
                    }

                    "batch_update" -> {
                        println("[BridgeTransport] 🔄 Batch update")
                        // Read updates array
                        val updates = obj["updates"]
                        if (updates != null) {
                            // Send each element via applyUpdate
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
                        // Notify BridgeState of new list
                        BridgeState.onThemeTokensReceived?.invoke(text)
                        println("[BridgeTransport] 🎨 Theme tokens received")
                    }

                    "analyze_element_response" -> {
                        println("[BridgeTransport] 📥 analyze_element_response received")
                        val responseRequestId = obj["request_id"]?.jsonPrimitive?.longOrNull ?: 0L
                        if (responseRequestId > 0 && responseRequestId != BridgeState.currentRequestId) {
                            println("[BridgeTransport] ⏭️ Ignoring stale response (id=$responseRequestId vs ${BridgeState.currentRequestId})")
                        } else {
                            try {
                                val resObj = obj["result"]?.jsonObject
                                if (resObj != null) {
                                    val cName = resObj["composable_name"]?.jsonPrimitive?.contentOrNull ?: "Element"
                                    val targetFile = resObj["source_file"]?.jsonPrimitive?.contentOrNull
                                        ?: obj["root"]?.jsonObject?.get("sourceFile")?.jsonPrimitive?.contentOrNull
                                    if (!targetFile.isNullOrEmpty()) {
                                        DesignModeRegistry.selectedSourceFile = targetFile
                                    }
                                    val colorsArray = resObj["colors"]?.jsonArray
                                    val parsedColors = mutableListOf<ElementColorInfo>()
                                    colorsArray?.forEach { cElem ->
                                        val cObj = cElem.jsonObject
                                        val occArray = cObj["occurrences_in_element"]?.jsonArray
                                        val occs = occArray?.mapNotNull { oElem ->
                                            val oObj = oElem.jsonObject
                                            val l = oObj["line"]?.jsonPrimitive?.intOrNull ?: return@mapNotNull null
                                            val p = oObj["property"]?.jsonPrimitive?.contentOrNull ?: "color"
                                            ElementColorOccurrence(l, p)
                                        } ?: emptyList()

                                        val locArray = cObj["locations"]?.jsonArray
                                        val locs = locArray?.mapNotNull { lElem ->
                                            val lObj = lElem.jsonObject
                                            val f = lObj["file"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                                            val l = lObj["line"]?.jsonPrimitive?.intOrNull ?: return@mapNotNull null
                                            val p = lObj["property"]?.jsonPrimitive?.contentOrNull ?: ""
                                            ElementColorLocation(f, l, p)
                                        } ?: emptyList()

                                        val isThemeDep = cObj["is_theme_dependent"]?.jsonPrimitive?.booleanOrNull ?: false
                                        parsedColors.add(
                                            ElementColorInfo(
                                                name = cObj["name"]?.jsonPrimitive?.contentOrNull ?: "Color",
                                                value = cObj["value"]?.jsonPrimitive?.contentOrNull ?: "#000000",
                                                usageGlobal = cObj["usage_global"]?.jsonPrimitive?.intOrNull ?: 1,
                                                usageInElement = cObj["usage_in_element"]?.jsonPrimitive?.intOrNull ?: 1,
                                                isShared = cObj["is_shared"]?.jsonPrimitive?.booleanOrNull ?: false,
                                                isToken = cObj["is_token"]?.jsonPrimitive?.booleanOrNull ?: false,
                                                property = cObj["property"]?.jsonPrimitive?.contentOrNull ?: "color",
                                                lineInElement = cObj["line_in_element"]?.jsonPrimitive?.intOrNull ?: 0,
                                                occurrencesInElement = occs,
                                                locations = locs,
                                                isThemeDependent = isThemeDep,
                                            )
                                        )
                                    }
                                    val dimsArray = resObj["dimension_details"]?.jsonArray
                                    val parsedDimensions = mutableListOf<ElementDimensionInfo>()
                                    dimsArray?.forEach { dElem ->
                                        try {
                                            val dObj = dElem.jsonObject
                                            val prop = dObj["property"]?.jsonPrimitive?.contentOrNull ?: ""
                                            val valStr = dObj["value"]?.jsonPrimitive?.contentOrNull ?: ""
                                            val num = dObj["number"]?.jsonPrimitive?.contentOrNull?.toFloatOrNull() ?: 0f
                                            val kind = dObj["kind"]?.jsonPrimitive?.contentOrNull ?: "dp"
                                            val line = dObj["line"]?.jsonPrimitive?.intOrNull ?: 0
                                            val defVal = dObj["default_value"]?.jsonPrimitive?.contentOrNull?.toFloatOrNull() ?: num
                                            val curVal = dObj["current_value"]?.jsonPrimitive?.contentOrNull?.toFloatOrNull() ?: num
                                            val isTernary = dObj["is_ternary"]?.jsonPrimitive?.booleanOrNull ?: false
                                            val desktopVal = dObj["desktop_value"]?.jsonPrimitive?.contentOrNull?.toFloatOrNull()
                                            val mobileVal = dObj["mobile_value"]?.jsonPrimitive?.contentOrNull?.toFloatOrNull()
                                            val usageGlobal = dObj["usage_global"]?.jsonPrimitive?.intOrNull ?: 0
                                            val isShared = dObj["is_shared"]?.jsonPrimitive?.booleanOrNull ?: (usageGlobal > 1)
                                            val dimFile = dObj["file"]?.jsonPrimitive?.contentOrNull ?: targetFile ?: ""
                                            val inShared = dObj["in_shared_function"]?.jsonPrimitive?.booleanOrNull ?: false
                                            val funcName = dObj["function_name"]?.jsonPrimitive?.contentOrNull ?: ""
                                            val funcCount = dObj["function_call_count"]?.jsonPrimitive?.intOrNull ?: 0
                                            val regKey = dObj["registry_key"]?.jsonPrimitive?.contentOrNull ?: ""
                                            val isWrapped = dObj["is_registry_wrapped"]?.jsonPrimitive?.booleanOrNull ?: false
                                            val locsArray = dObj["locations"]?.jsonArray
                                            val parsedLocations = locsArray?.mapNotNull { locElem ->
                                                try {
                                                    val lObj = locElem.jsonObject
                                                    val f = lObj["file"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                                                    val l = lObj["line"]?.jsonPrimitive?.intOrNull ?: return@mapNotNull null
                                                    val p = lObj["property"]?.jsonPrimitive?.contentOrNull ?: ""
                                                    ElementColorLocation(file = f, line = l, property = p)
                                                } catch (e: Exception) { null }
                                            } ?: emptyList()

                                            parsedDimensions.add(
                                                ElementDimensionInfo(
                                                    property = prop,
                                                    value = valStr,
                                                    number = num,
                                                    kind = kind,
                                                    line = line,
                                                    defaultValue = defVal,
                                                    currentValue = curVal,
                                                    isTernary = isTernary,
                                                    desktopValue = desktopVal,
                                                    mobileValue = mobileVal,
                                                    usageGlobal = usageGlobal,
                                                    isShared = isShared,
                                                    locations = parsedLocations,
                                                    file = dimFile,
                                                    inSharedFunction = inShared,
                                                    functionName = funcName,
                                                    functionCallCount = funcCount,
                                                    registryKey = regKey,
                                                    isRegistryWrapped = isWrapped,
                                                )
                                            )
                                        } catch (e: Exception) {
                                            println("[BridgeTransport] ⚠️ Error parsing dimension: $e")
                                        }
                                    }

                                    val textsArray = resObj["texts"]?.jsonArray
                                    val parsedTexts = mutableListOf<ElementTextInfo>()
                                    textsArray?.forEach { tElem ->
                                        try {
                                            val tObj = tElem.jsonObject
                                            val textVal = tObj["text"]?.jsonPrimitive?.contentOrNull ?: ""
                                            if (textVal.isNotEmpty()) {
                                                val tFile = tObj["file"]?.jsonPrimitive?.contentOrNull ?: targetFile ?: ""
                                                val tLine = tObj["line"]?.jsonPrimitive?.intOrNull ?: 1
                                                val isRef = tObj["is_resource_or_ref"]?.jsonPrimitive?.booleanOrNull ?: false
                                                val rKey = tObj["ref_key"]?.jsonPrimitive?.contentOrNull
                                                val prop = tObj["property"]?.jsonPrimitive?.contentOrNull ?: "text"

                                                // If server returned template code ($ or {), prefer evaluated text from device screen
                                                val cleanVal = if (textVal.contains("$") || textVal.contains("{")) {
                                                    BridgeState.lastEvaluatedScreenText?.takeIf { it.isNotBlank() } ?: textVal
                                                } else {
                                                    textVal
                                                }
                                                val finalProp = if (!rKey.isNullOrEmpty() && rKey.startsWith("AppStrings.")) rKey else prop
                                                val finalIsRef = isRef || (!rKey.isNullOrEmpty() && rKey.startsWith("AppStrings."))
                                                parsedTexts.add(
                                                    ElementTextInfo(
                                                        text = cleanVal,
                                                        file = tFile,
                                                        line = tLine,
                                                        property = finalProp,
                                                        isResourceOrRef = finalIsRef,
                                                        refKey = rKey
                                                    )
                                                )
                                            }
                                        } catch (e: Exception) {
                                            println("[BridgeTransport] Error parsing text: $e")
                                        }
                                    }

                                    mainHandler.post {
                                        BridgeState.elementComposableName = cName
                                        BridgeState.elementColors.clear()
                                        BridgeState.elementColors.addAll(parsedColors)
                                        BridgeState.elementDimensions.clear()
                                        BridgeState.elementDimensions.addAll(parsedDimensions)
                                        BridgeState.elementTexts.clear()
                                        BridgeState.elementTexts.addAll(parsedTexts)
                                        BridgeState.isLoadingElementColors = false
                                        BridgeState.elementAnalysisError = null
                                    }
                                }
                            } catch (e: Exception) {
                                println("[BridgeTransport] ⚠️ Error parsing analyze_element_response: $e")
                            }
                            BridgeState.onElementAnalyzed?.invoke(text)
                        }
                    }

                    "split_token_response" -> {
                        val success = obj["success"]?.jsonPrimitive?.booleanOrNull ?: false
                        val newToken = obj["new_token"]?.jsonPrimitive?.contentOrNull
                        val newHex = obj["new_value_hex"]?.jsonPrimitive?.contentOrNull
                        if (success && newToken != null) {
                            println("[BridgeTransport] ✂️ Split token success: $newToken")
                            if (newHex != null) {
                                BridgeThemeRegistry.setColorHex(newToken, newHex)
                            }
                            mainHandler.post {
                                BridgeState.onSplitTokenSuccess?.invoke(newToken)
                            }
                        }
                    }

                    "global_color_edit_ack" -> {
                        val status = obj["status"]?.jsonPrimitive?.contentOrNull
                        val res = obj["result"]?.jsonObject
                        val success = status == "ok" || res?.get("success")?.jsonPrimitive?.booleanOrNull == true
                        println("[BridgeTransport] 🌍 global_color_edit_ack: status=$status, success=$success")
                        mainHandler.post {
                            val file = DesignModeRegistry.selectedSourceFile
                            val line = DesignModeRegistry.selectedSourceLine
                            if (file != null && line != null) {
                                ComposeBridgeAgent.analyzeElementWithTree(file, line)
                            }
                        }
                    }

                    "split_token_ack" -> {
                        val status = obj["status"]?.jsonPrimitive?.contentOrNull
                        println("[BridgeTransport] ✂️ split_token_ack: status=$status")
                        mainHandler.post {
                            val file = DesignModeRegistry.selectedSourceFile
                            val line = DesignModeRegistry.selectedSourceLine
                            if (file != null && line != null) {
                                ComposeBridgeAgent.analyzeElementWithTree(file, line)
                            }
                        }
                    }

                    "refresh_element_request" -> {
                        println("[BridgeTransport] 🔄 refresh_element_request received")
                        mainHandler.post {
                            val file = DesignModeRegistry.selectedSourceFile
                            val line = DesignModeRegistry.selectedSourceLine
                            if (file != null && line != null) {
                                ComposeBridgeAgent.analyzeElementWithTree(file, line)
                            }
                        }
                    }

                    "batch_progress" -> {
                        val status = obj["status"]?.jsonPrimitive?.contentOrNull
                        val current = obj["current"]?.jsonPrimitive?.intOrNull ?: 0
                        val total = obj["total"]?.jsonPrimitive?.intOrNull ?: 0
                        val token = obj["current_token"]?.jsonPrimitive?.contentOrNull ?: ""
                        println("[BridgeTransport] ⏳ batch_progress: status=$status, current=$current/$total, token=$token")
                        mainHandler.post {
                            when (status) {
                                "started" -> {
                                    val msg = "⏳ Processing $total change(s)..."
                                    BridgeState.batchMessage = msg
                                    BridgeState.showSnackbar(msg)
                                }
                                "in_progress" -> {
                                    val msg = "⏳ $current/$total — $token"
                                    BridgeState.batchMessage = msg
                                    BridgeState.showSnackbar(msg)
                                }
                            }
                        }
                    }

                    "batch_edits_ack" -> {
                        val successCount = obj["success_count"]?.jsonPrimitive?.intOrNull ?: 0
                        val failCount = obj["fail_count"]?.jsonPrimitive?.intOrNull ?: obj["failed_count"]?.jsonPrimitive?.intOrNull ?: 0
                        val total = obj["total"]?.jsonPrimitive?.intOrNull ?: 0
                        println("[BridgeTransport] 📦 batch_edits_ack: success=$successCount, fail=$failCount, total=$total")

                        val resultsArray = obj["results"]?.jsonArray
                        val convertedHardcoded = resultsArray?.any { item ->
                            item.jsonObject["result"]?.jsonObject?.get("converted_hardcoded")?.jsonPrimitive?.booleanOrNull == true
                        } ?: false

                        mainHandler.post {
                            BridgeState.syncInProgress = false
                            if (convertedHardcoded) {
                                BridgeState.pendingRebuild = true
                                BridgeState.lastGlobalEditInfo = "🎨 Converted — Rebuild required to see changes"
                            }

                            val allIds = resultsArray
                                ?.mapNotNull { it.jsonObject["id"]?.jsonPrimitive?.contentOrNull }
                                ?.toSet() ?: emptySet()

                            if (allIds.isNotEmpty()) {
                                BridgeState.onBatchAck(allIds)
                            } else {
                                BridgeState.clearPendingEdits(revert = false)
                            }

                            if (failCount == 0) {
                                if (convertedHardcoded) {
                                    BridgeState.showSnackbar("✅ Converted ($successCount/$total) — Rebuild required")
                                } else {
                                    BridgeState.showSnackbar("✅ Applied $successCount/$total")
                                }
                            } else {
                                BridgeState.showSnackbar("⚠️ $successCount succeeded, $failCount failed")
                            }

                            val file = DesignModeRegistry.selectedSourceFile
                            val line = DesignModeRegistry.selectedSourceLine
                            if (file != null && line != null) {
                                ComposeBridgeAgent.analyzeElementWithTree(file, line)
                            }
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

                    "reject_all_files_ack", "reject_all_ack" -> {
                        mainHandler.post {
                            BridgeThemeRegistry.clearAll()
                            BridgeState.clearPendingEdits(revert = false)
                            BridgeState.showSnackbar("🗑 All changes reverted")
                            println("[BridgeTransport] 🗑 Reject all received: cleared theme & pending edits")
                        }
                    }

                    // ⭐ Agent status from server.py
                    "agent_status" -> {
                        val busy = obj["agent_busy"]?.jsonPrimitive?.booleanOrNull ?: false
                        val queuePending = obj["queue_pending"]?.jsonPrimitive?.intOrNull
                        
                        println("[BridgeTransport] 🤖 Agent status: busy=$busy")
                        BridgeState.setAgentBusy(busy)
                        
                        if (queuePending != null) {
                            BridgeState.setQueueCount(queuePending)
                        }
                        
                        BridgeState.onAgentStatusChanged?.invoke(busy)
                    }
                    
                    // ⭐ Queue status response
                    "queue_status_response" -> {
                        val count = obj["count"]?.jsonPrimitive?.intOrNull ?: 0
                        val busy = obj["agent_busy"]?.jsonPrimitive?.booleanOrNull ?: false
                        
                        println("[BridgeTransport] 📥 Queue status: count=$count, busy=$busy")
                        BridgeState.setQueueCount(count)
                        BridgeState.setAgentBusy(busy)
                    }
                    
                    // ⭐ Queue clear ack
                    "queue_clear_ack" -> {
                        val cleared = obj["cleared"]?.jsonPrimitive?.intOrNull ?: 0
                        println("[BridgeTransport] 🗑️ Queue cleared: $cleared edits")
                        BridgeState.setQueueCount(0)
                    }
                    
                    // ⭐ Update ack — may be queued
                    "update_token_default_ack" -> {
                        val status = obj["status"]?.jsonPrimitive?.contentOrNull
                        val queuePosition = obj["queue_position"]?.jsonPrimitive?.intOrNull
                        val busy = obj["agent_busy"]?.jsonPrimitive?.booleanOrNull ?: false
                        
                        println("[BridgeTransport] 📩 update_token_default_ack: status=$status, pos=$queuePosition")
                        
                        if (status == "queued" && queuePosition != null) {
                            BridgeState.setQueueCount(queuePosition)
                            BridgeState.setAgentBusy(true)
                        } else if (status == "ok") {
                            // ⭐ Do not reset queueCount — old edits may still be pending
                            // Request actual state from server
                            ComposeBridgeAgent.requestQueueStatus()
                        }
                    }
                    // ⭐ Color update ack — may be queued
                    "state_update_ack" -> {
                        val status = obj["status"]?.jsonPrimitive?.contentOrNull
                        val queuePos = obj["queue_position"]?.jsonPrimitive?.intOrNull
                        val prop = obj["property"]?.jsonPrimitive?.contentOrNull
                        
                        println("[BridgeTransport] 📩 state_update_ack: status=$status")
                        
                        if (status == "queued" && queuePos != null) {
                            println("[BridgeTransport] 📥 Color queued at pos=$queuePos")
                            BridgeState.setQueueCount(queuePos)
                            BridgeState.setAgentBusy(true)
                        } else {
                            BridgeState.requestQueueStatus()
                        }
                    }

                    // ⭐ User sync ack
                    "user_sync_ack" -> {
                        val status = obj["status"]?.jsonPrimitive?.contentOrNull
                        val applied = obj["applied"]?.jsonPrimitive?.intOrNull ?: 0
                        val skipped = obj["skipped"]?.jsonPrimitive?.intOrNull ?: 0
                        val errors = obj["errors"]?.jsonPrimitive?.intOrNull ?: 0
                        val message = obj["message"]?.jsonPrimitive?.contentOrNull
                        val reason = obj["reason"]?.jsonPrimitive?.contentOrNull
                        
                        println("[BridgeTransport] 📩 user_sync_ack: status=$status, applied=$applied, skipped=$skipped")
                        
                        BridgeState.setSyncing(false)
                        
                        val displayMessage = when (status) {
                            "ok" -> if (applied > 0) "✅ Applied $applied change(s) successfully"
                                    else "No pending changes"
                            "partial" -> "⚠️ $applied succeeded — $skipped skipped (token not found)"
                            "failed" -> "❌ Failed — $skipped token(s) not found"
                            "error" -> "❌ Error in $errors change(s)"
                            "refused" -> if (reason == "agent_busy") "⚠️ Agent busy — try again later" else "⚠️ Sync rejected"
                            else -> message ?: "⚠️ Unknown status"
                        }
                        
                        BridgeState.setSyncResult(displayMessage)
                        
                        if (applied > 0 || status == "partial" || status == "failed") {
                            BridgeState.setQueueCount(0)
                        } else {
                            BridgeState.requestQueueStatus()
                        }
                    }

                    "add_token_ack" -> {
                        val status = obj["status"]?.jsonPrimitive?.contentOrNull
                        val warning = obj["warning"]?.jsonPrimitive?.contentOrNull
                        if (warning != null) {
                            BridgeState.setSyncResult("⚠️ $warning")
                        }
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
            BridgeState.connectionStatusText = "Disconnected"
        }
    }
}
