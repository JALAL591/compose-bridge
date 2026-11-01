package com.composebridge.agent

import android.app.Activity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.InternalComposeApi
import androidx.compose.runtime.currentComposer
import androidx.compose.runtime.tooling.LocalInspectionTables
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

import androidx.compose.runtime.getValue
import kotlinx.serialization.json.*

@OptIn(InternalComposeApi::class)
object ComposeBridgeAgent {

    private val registry = CompositionRegistry()
    internal var transport: BridgeTransport? = null
    @Volatile internal var appContext: android.content.Context? = null

    private fun isAppDebuggable(context: android.content.Context?): Boolean {
        val ctx = context ?: return true
        return (ctx.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0
    }

    @Composable
    fun Root(content: @Composable () -> Unit) {
        val context = androidx.compose.ui.platform.LocalContext.current
        if (!isAppDebuggable(context)) {
            // In release builds, render the user content directly with zero overhead, zero buttons, and zero overlays
            content()
            return
        }
        currentComposer.collectParameterInformation()
        registry.register(currentComposer.compositionData)
        androidx.compose.runtime.DisposableEffect(context) {
            (context as? Activity)?.let { activity ->
                attachOverlay(activity)
            }
            onDispose {
                detachOverlay()
            }
        }
        CompositionLocalProvider(
            LocalInspectionTables provides registry.tables
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                content()
                DesignModeButton(
                    modifier = Modifier
                        .align(Alignment.CenterEnd)
                        .statusBarsPadding()
                        .padding(top = 80.dp, end = 16.dp)
                )
                GlobalPanels()
            }
        }
    }

    private const val PREFS_NAME = "composebridge_prefs"
    private const val KEY_AUTH_TOKEN = "composebridge_auth_token"
    private const val KEY_REMOTE_URL = "composebridge_remote_url"
    private const val KEY_LOCAL_URL = "composebridge_local_url"
    private const val KEY_IS_REMOTE = "composebridge_is_remote"
    @Volatile var isRemoteMode: Boolean = false
    private var tokenReceiver: android.content.BroadcastReceiver? = null

    fun start(
        serverUrl: String = "ws://127.0.0.1:8711",
        authToken: String = "",
        context: android.content.Context? = null
    ) {
        if (context != null) {
            BridgeBackgroundService.start(context)
        }
        if (context != null && !isAppDebuggable(context)) {
            println("[ComposeBridge] ⚠️ Disabled in release builds")
            return
        }

        if (context != null) {
            appContext = context.applicationContext ?: context
        }
        var resolvedToken = authToken
        var resolvedUrl = serverUrl

        if (context != null) {
            val prefs = context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
            if (serverUrl.isNotBlank() && !serverUrl.startsWith("wss://")) {
                prefs.edit().putString(KEY_LOCAL_URL, serverUrl).apply()
            }
            resolvedUrl = getActiveUrl(context)
            if (resolvedToken.isBlank()) {
                resolvedToken = prefs.getString(KEY_AUTH_TOKEN, "") ?: ""
            }
        }

        if (transport != null) {
            if (resolvedToken.isNotBlank()) {
                transport?.updateAuthToken(resolvedToken)
            }
            if (resolvedUrl.isNotBlank() && resolvedUrl != transport?.getServerUrl()) {
                transport?.updateServerUrl(resolvedUrl)
            }
            return
        }
        transport = BridgeTransport(
            serverUrl = resolvedUrl,
            registry = registry,
            authToken = resolvedToken,
            urlProvider = { context?.let { getActiveUrl(it) } ?: resolvedUrl },
            contextProvider = { appContext ?: context }
        )
        transport?.connect()
    }

    fun setAuthToken(context: android.content.Context, token: String) {
        context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_AUTH_TOKEN, token)
            .apply()
        transport?.updateAuthToken(token)
        transport?.reconnect()
    }

    fun connectRemote(context: android.content.Context, remoteUrl: String, token: String) {
        val cleanUrl = remoteUrl.trim()
        val cleanToken = token.trim()

        isRemoteMode = true
        appContext = context.applicationContext ?: context

        val editor = context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE).edit()
        editor.putBoolean(KEY_IS_REMOTE, true)
        editor.putString(KEY_REMOTE_URL, cleanUrl)
        if (cleanToken.isNotBlank()) {
            editor.putString(KEY_AUTH_TOKEN, cleanToken)
        }
        editor.apply()

        android.util.Log.i("ComposeBridge", "🌍 Switched to REMOTE mode: $cleanUrl")

        try {
            transport?.disconnect()
            Thread.sleep(200)
        } catch (_: Exception) {}

        if (transport == null) {
            transport = BridgeTransport(
                serverUrl = cleanUrl,
                registry = registry,
                authToken = cleanToken,
                urlProvider = { getActiveUrl(context) },
                contextProvider = { appContext ?: context }
            )
            transport?.webSocketClient?.isRemoteMode = true
            transport?.connect()
        } else {
            transport?.webSocketClient?.isRemoteMode = true
            if (cleanToken.isNotBlank()) {
                transport?.updateAuthToken(cleanToken)
            }
            transport?.updateServerUrl(cleanUrl)
            transport?.connect()
        }
        BridgeState.showSnackbar("🌍 Connecting remotely: $cleanUrl")
    }

    fun resetToLocal(context: android.content.Context) {
        isRemoteMode = false
        appContext = context.applicationContext ?: context

        context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_IS_REMOTE, false)
            .apply()

        val localUrl = getLocalUrl(context)
        android.util.Log.i("ComposeBridge", "🔌 Switched to LOCAL mode: $localUrl")
        try {
            transport?.disconnect()
            Thread.sleep(200)
        } catch (_: Exception) {}
        if (transport != null) {
            transport?.webSocketClient?.isRemoteMode = false
            transport?.updateServerUrl(localUrl)
            transport?.connect()
        }
        BridgeState.showSnackbar("🔌 Returned to local connection (127.0.0.1)")
    }

    fun isRemoteMode(context: android.content.Context): Boolean {
        return context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .getBoolean(KEY_IS_REMOTE, false)
    }

    fun getActiveUrl(context: android.content.Context? = null): String {
        if (context != null) {
            val prefs = context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
            val isRemote = prefs.getBoolean(KEY_IS_REMOTE, false)
            if (isRemote) {
                val remote = prefs.getString(KEY_REMOTE_URL, "") ?: ""
                if (remote.isNotBlank()) return remote
            }
            return prefs.getString(KEY_LOCAL_URL, "ws://127.0.0.1:8711") ?: "ws://127.0.0.1:8711"
        }
        return transport?.getServerUrl() ?: "ws://127.0.0.1:8711"
    }

    fun getLocalUrl(context: android.content.Context): String {
        return context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .getString(KEY_LOCAL_URL, "ws://127.0.0.1:8711") ?: "ws://127.0.0.1:8711"
    }

    fun getSavedRemoteUrl(context: android.content.Context): String {
        return context.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
            .getString(KEY_REMOTE_URL, "") ?: ""
    }

    fun applyQrPayload(context: android.content.Context, payload: String): Boolean {
        android.util.Log.d("ComposeBridge", "📥 applyQrPayload received: $payload")
        return try {
            val trimmed = payload.trim()
            val (url, token) = if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
                val element = Json.parseToJsonElement(trimmed)
                val obj = element.jsonObject
                val u = obj["url"]?.jsonPrimitive?.content ?: ""
                val t = obj["token"]?.jsonPrimitive?.content ?: ""
                Pair(u, t)
            } else if (trimmed.startsWith("ws://") || trimmed.startsWith("wss://")) {
                Pair(trimmed, "")
            } else {
                Pair("", "")
            }

            if (url.isNotBlank()) {
                connectRemote(context, url, token)
                true
            } else {
                android.util.Log.w("ComposeBridge", "⚠️ No valid url found in QR payload")
                false
            }
        } catch (e: Exception) {
            android.util.Log.e("ComposeBridge", "❌ Failed to parse QR payload: ${e.message}")
            false
        }
    }

    fun stop() {
        transport?.close()
        transport = null
    }

    fun disconnect() {
        transport?.disconnect()
    }

    fun reconnect() {
        transport?.reconnect()
    }

    /**
     * Attaches Overlay to Activity (called from onResume)
     */
    fun attachOverlay(activity: Activity) {
        BridgeBackgroundService.start(activity)
        if (!isAppDebuggable(activity)) return
        BridgeOverlayManager.attach(activity)

        // Read token from SharedPreferences if current transport has empty token
        val prefs = activity.getSharedPreferences(PREFS_NAME, android.content.Context.MODE_PRIVATE)
        val savedToken = prefs.getString(KEY_AUTH_TOKEN, "") ?: ""
        if (savedToken.isNotBlank()) {
            transport?.updateAuthToken(savedToken)
        }

        // Register ADB BroadcastReceivers (SET_TOKEN, SET_REMOTE, RESET_LOCAL)
        if (tokenReceiver == null) {
            val receiver = object : android.content.BroadcastReceiver() {
                override fun onReceive(c: android.content.Context?, intent: android.content.Intent?) {
                    when (intent?.action) {
                        "com.composebridge.SET_TOKEN" -> {
                            val newToken = intent.getStringExtra("token")
                            if (!newToken.isNullOrBlank()) {
                                android.util.Log.d("ComposeBridge", "🔑 Received auth token via ADB broadcast: ${newToken.take(8)}...")
                                setAuthToken(activity, newToken)
                            }
                        }
                        "com.composebridge.SET_REMOTE" -> {
                            val url = intent.getStringExtra("url") ?: ""
                            val token = intent.getStringExtra("token") ?: ""
                            if (url.isNotBlank()) {
                                android.util.Log.d("ComposeBridge", "🌍 Received remote URL via ADB: $url")
                                connectRemote(activity, url, token)
                            }
                        }
                        "com.composebridge.RESET_LOCAL" -> {
                            android.util.Log.d("ComposeBridge", "🔌 Reset to local via ADB")
                            resetToLocal(activity)
                        }
                    }
                }
            }
            val filter = android.content.IntentFilter().apply {
                addAction("com.composebridge.SET_TOKEN")
                addAction("com.composebridge.SET_REMOTE")
                addAction("com.composebridge.RESET_LOCAL")
            }
            try {
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                    activity.registerReceiver(receiver, filter, android.content.Context.RECEIVER_EXPORTED)
                } else {
                    activity.registerReceiver(receiver, filter)
                }
                tokenReceiver = receiver
            } catch (e: Exception) {
                android.util.Log.w("ComposeBridge", "Failed to register SET_TOKEN receiver: ${e.message}")
            }
        }
    }

    fun detachOverlay() {
        BridgeOverlayManager.detach()
    }

    /**
     * Enables/disables design mode
     */
    fun setSelectionMode(enabled: Boolean) {
        BridgeOverlayManager.setActive(enabled)
    }

    fun isSelectionMode(): Boolean = BridgeOverlayManager.isActive()

    /**
     * Snapshot of all user components
     */
    fun getAllUserNodes(): List<BridgeNode> {
        return registry.snapshot().flatMap { table ->
            table.toBridgeTree()?.collectUserNodes() ?: emptyList()
        }
    }

    /**
     * Sends state update to Python bridge via WebSocket.
     * Python bridge persists it to file.
     */
    fun sendStateUpdate(property: String, value: String): Boolean {
        if (property.startsWith("AppColors.")) {
            val simpleKey = property.removePrefix("AppColors.").trim()
            BridgeThemeRegistry.setColorHex(simpleKey, value)
            println("[ComposeBridgeAgent] 🎨 Local apply: $simpleKey = $value")
        }
        val json = """
            {"type":"state_update","property":"$property","value":"$value"}
        """.trimIndent()
        return transport?.send(json) ?: false
    }

    /**
     * Requests Theme Tokens list from Python bridge.
     */
    fun requestThemeTokens(): Boolean {
        val json = """{"type":"theme_tokens"}"""
        return transport?.send(json) ?: false
    }

    /**
     * Requests token color update.
     */
    fun sendColorUpdate(tokenKey: String, newHex: String): Boolean {
        val simpleKey = tokenKey.removePrefix("AppColors.").trim()
        BridgeThemeRegistry.setColorHex(simpleKey, newHex)
        println("[ComposeBridgeAgent] 🎨 Local apply: $simpleKey = $newHex")
        val json = """
            {"type":"state_update","property":"AppColors.$simpleKey","value":"$newHex"}
        """.trimIndent()
        return transport?.send(json) ?: false
    }

    /**
     * Requests element analysis from Python bridge.
     */
    fun analyzeElement(
        file: String,
        line: Int,
        utf16Offset: Int = 0,
        utf16Length: Int = 0,
        requestId: Long = 0L,
    ): Boolean {
        val json = """
            {"type":"analyze_element","file":"$file","line":$line,"offset":$utf16Offset,"length":$utf16Length,"request_id":$requestId}
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
        val jsonReal = """
            {"type":"edit_dimension","file":"$file","line":$line,"offset":$offset,"length":$length,"oldValue":"$oldValue","newValue":"$newValue"}
        """.trimIndent()
        return transport?.send(jsonReal) ?: false
    }

    /**
     * Sends dimension_override to Python bridge and updates Registry.
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
     * Sends default Token update for BridgeSpacing.kt
     */
    fun sendTokenDefault(tokenName: String, value: String): Boolean {
        val json = """
            {"type":"update_token_default","token":"$tokenName","value":"$value"}
        """.trimIndent()
        return transport?.send(json) ?: false
    }

    /**
     * Requests element analysis with children tree.
     */
            fun analyzeElementWithTree(
        file: String,
        line: Int,
        utf16Offset: Int = 0,
        utf16Length: Int = 0,
        treeJson: String = "[]",
        requestId: Long = 0L,
        parentFile: String? = null,
        parentLine: Int? = null,
        textValue: String? = null,
        textReference: String? = null,
        mode: String = BridgeState.currentEditMode.name,
    ): Boolean {
        val quote = '"'
        val slash = '\\'
        val escapedTree = treeJson.replace(quote.toString(), "$slash$quote")
        val pFilePart = if (parentFile != null) ",${quote}parent_file${quote}:${quote}$parentFile${quote}" else ""
        val pLinePart = if (parentLine != null) ",${quote}parent_line${quote}:$parentLine" else ""
        val escapedTxtVal = textValue?.replace(slash.toString(), "$slash$slash")?.replace(quote.toString(), "$slash$quote")?.replace("\n", "${slash}n")
        val tValPart = if (escapedTxtVal != null) ",${quote}text_value${quote}:${quote}$escapedTxtVal${quote}" else ""
        val tRefPart = if (textReference != null) ",${quote}text_reference${quote}:${quote}$textReference${quote}" else ""
        val json = """{"type":"analyze_element_with_tree","file":"$file","line":$line,"offset":$utf16Offset,"length":$utf16Length,"tree":"$escapedTree","request_id":$requestId,"mode":"$mode"$pFilePart$pLinePart$tValPart$tRefPart}"""
        return transport?.send(json) ?: false
    }

    /**
     * Requests Queue status from Bridge.
     */
    fun requestQueueStatus(): Boolean {
        val json = """{"type":"queue_status"}"""
        return transport?.send(json) ?: false
    }
    
    /**
     * Requests clearing the Queue.
     */
    fun requestQueueClear(): Boolean {
        val json = """{"type":"queue_clear"}"""
        return transport?.send(json) ?: false
    }
    
    /**
     * Requests applying the Queue (Sync).
     */
    fun requestUserSync(): Boolean {
        val json = """{"type":"user_sync"}"""
        return transport?.send(json) ?: false
    }

    /**
     * Requests global color update for all occurrences in project.
     */
    fun sendGlobalColorEdit(
        file: String,
        line: Int,
        oldValue: String,
        newValue: String,
        tokenName: String,
    ): Boolean {
        val escapedFile = file.replace("\"", "\\\"")
        val escapedOld = oldValue.replace("\"", "\\\"")
        val escapedNew = newValue.replace("\"", "\\\"")
        val escapedToken = tokenName.replace("\"", "\\\"")
        val json = """
            {"type":"global_color_edit","file":"$escapedFile","line":$line,"old_value":"$escapedOld","new_value":"$escapedNew","token_name":"$escapedToken"}
        """.trimIndent()
        return transport?.send(json) ?: false
    }

    /**
     * Requests creating dedicated token and splitting shared token (Focus Mode Split).
     */
    fun sendSplitToken(
        originalToken: String,
        originalValue: String,
        newTokenName: String,
        newValue: String,
        elementFile: String,
        elementLine: Int,
        occurrencesJson: String,
    ): Boolean {
        val escapedOrig = originalToken.replace("\"", "\\\"")
        val escapedVal = originalValue.replace("\"", "\\\"")
        val escapedToken = newTokenName.replace("\"", "\\\"")
        val escapedNew = newValue.replace("\"", "\\\"")
        val escapedFile = elementFile.replace("\"", "\\\"")
        val json = """
            {"type":"split_token","original_token":"$escapedOrig","original_value":"$escapedVal","new_token_name":"$escapedToken","new_value":"$escapedNew","element_file":"$escapedFile","element_line":$elementLine,"occurrences_in_element":$occurrencesJson}
        """.trimIndent()
        return transport?.send(json) ?: false
    }

    private var isSendingBatch = false

    /**
     * Sends batch of pending edits at once.
     */
    fun sendBatchEdits(edits: List<PendingEdit>): Boolean {
        if (edits.isEmpty()) return false
        if (isSendingBatch) {
            println("[ComposeBridgeAgent] ⚠️ sendBatchEdits already in progress, ignoring duplicate call")
            return false
        }
        isSendingBatch = true

        try {
            // Deduplicate by ID and by target element / property
            val deduplicatedEdits = edits.reversed()
                .distinctBy { it.id }
                .distinctBy {
                    if (it.file.isNotEmpty() && it.line > 0) {
                        "${it.file}:${it.line}:${it.property}"
                    } else if (it.tokenName.isNotEmpty()) {
                        "${it.tokenName}:${it.property}"
                    } else {
                        it.id
                    }
                }
                .reversed()

            if (deduplicatedEdits.isEmpty()) {
                BridgeState.syncInProgress = false
                return false
            }

            BridgeState.syncInProgress = true

            val editsArray = deduplicatedEdits.map { edit ->
                kotlinx.serialization.json.buildJsonObject {
                    put("id", edit.id)
                    put("type", edit.type)
                    put("file", edit.file)
                    put("line", edit.line)
                    put("property", edit.property)
                    put("old_value", edit.oldValue)
                    put("new_value", edit.newValue)
                    put("token_name", edit.tokenName)
                    edit.originalToken?.let { put("original_token", it) }
                    edit.originalValue?.let { put("original_value", it) }
                    edit.refKey?.let {
                        put("ref_key", it)
                        put("text_reference", it)
                        put("target", it)
                    }
                    if (edit.occurrences.isNotEmpty()) {
                        put("occurrences", kotlinx.serialization.json.buildJsonArray {
                            edit.occurrences.forEach { occ ->
                                add(kotlinx.serialization.json.buildJsonObject {
                                    put("line", occ.line)
                                    put("property", occ.property)
                                })
                            }
                        })
                    } else if (!edit.occurrencesJson.isNullOrBlank()) {
                        try {
                            put("occurrences", kotlinx.serialization.json.Json.parseToJsonElement(edit.occurrencesJson))
                        } catch (e: Exception) {
                            put("occurrences", edit.occurrencesJson)
                        }
                    }
                    edit.dimensionToken?.let { put("dimension_token", it) }
                    edit.dimensionValue?.let { put("dimension_value", it.toDouble()) }
                    if (edit.type == "dimension") {
                        put("is_ternary", edit.isTernary)
                        edit.desktopValue?.let { put("desktop_value", it.toDouble()) }
                        put("is_shared", edit.isShared)
                        put("edit_mode", edit.editMode)
                        put("dimension_kind", edit.dimensionKind)
                        if (edit.registryKey.isNotEmpty()) {
                            put("registry_key", edit.registryKey)
                        }
                    }
                }
            }
            val json = kotlinx.serialization.json.buildJsonObject {
                put("type", "batch_edits")
                put("edits", kotlinx.serialization.json.buildJsonArray {
                    editsArray.forEach { add(it) }
                })
            }.toString()

            val sent = transport?.send(json) ?: false
            if (!sent) {
                BridgeState.syncInProgress = false
            }
            return sent
        } finally {
            isSendingBatch = false
        }
    }

    /**
     * Reverts all pending changes and cleans theme.
     */
    fun rejectAll() {
        BridgeThemeRegistry.clearAll()
        BridgeState.clearPendingEdits(revert = false)
        val json = kotlinx.serialization.json.buildJsonObject {
            put("type", "reject_all_files")
        }.toString()
        transport?.send(json)
    }

    fun registry(): CompositionRegistry = registry

        /**
     * Requests list of modified files from the server.
     */
    fun buildAndSendApk(forceRebuild: Boolean = false) {
        com.composebridge.agent.services.ApkBuilder.buildAndSendApk(transport, forceRebuild)
    }

    fun fetchExistingApk() {
        com.composebridge.agent.services.ApkBuilder.fetchExistingApk(transport)
    }

    fun requestApkBuildStatus() {
        com.composebridge.agent.services.ApkBuilder.requestApkBuildStatus(transport)
    }

    fun requestModifiedFiles(): Boolean {
        android.util.Log.d("ComposeBridge", "📡 [ComposeBridgeAgent] requestModifiedFiles() called")
        BridgeState.isLoadingModifiedFiles = true
        val json = """{"type":"get_modified_files"}"""
        val t = transport
        if (t == null) {
            android.util.Log.e("ComposeBridge", "❌ [ComposeBridgeAgent] transport is NULL! Cannot request modified files.")
            return false
        }
        val sent = t.send(json)
        android.util.Log.d("ComposeBridge", "📡 [ComposeBridgeAgent] requestModifiedFiles() sent result: $sent")
        return sent
    }

    /**
     * Approves changes made to a specific file.
     */
    fun approveFile(file: String): Boolean {
        val escaped = file.replace("\"", "\\\"")
        val json = """{"type":"approve_file","file":"$escaped"}"""
        return transport?.send(json) ?: false
    }

    /**
     * Rejects/rolls back changes made to a specific file.
     */
    fun rejectFile(file: String, force: Boolean = false): Boolean {
        val escaped = file.replace("\"", "\\\"")
        val json = """{"type":"reject_file","file":"$escaped","force":$force}"""
        return transport?.send(json) ?: false
    }

    /**
     * Approves changes to all modified files.
     */
    fun approveAllFiles(): Boolean {
        val json = """{"type":"approve_all_files"}"""
        return transport?.send(json) ?: false
    }

    /**
     * Rejects changes to all modified files.
     */
    fun rejectAllFiles(force: Boolean = false): Boolean {
        val json = """{"type":"reject_all_files","force":$force}"""
        return transport?.send(json) ?: false
    }

    /**
     * Triggers remote Gradle build and downloads OTA APK to device.
     */
    fun buildAndSendApk(): Boolean {
        return com.composebridge.agent.services.ApkBuilder.buildAndSendApk(transport, false)
    }
}
