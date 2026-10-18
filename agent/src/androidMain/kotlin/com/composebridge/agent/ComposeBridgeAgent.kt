package com.composebridge.agent

import android.app.Activity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.InternalComposeApi
import androidx.compose.runtime.currentComposer
import androidx.compose.runtime.tooling.LocalInspectionTables
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import kotlinx.serialization.json.*

@OptIn(InternalComposeApi::class)
object ComposeBridgeAgent {

    private val registry = CompositionRegistry()
    private var transport: BridgeTransport? = null

    @Composable
    fun Root(content: @Composable () -> Unit) {
        val themeVersion by BridgeThemeRegistry.version
        val dimVersion by BridgeDimensionRegistry.version
        currentComposer.collectParameterInformation()
        registry.register(currentComposer.compositionData)
        val context = androidx.compose.ui.platform.LocalContext.current
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
                key(themeVersion, dimVersion) {
                    content()
                }
                DesignModeButton(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(16.dp)
                )
                GlobalPanels()
            }
        }
    }

    fun start(
        serverUrl: String = "ws://127.0.0.1:8711",
        authToken: String = "test-token-local-dev",
    ) {
        if (!BuildConfig.DEBUG) {
            println("[ComposeBridge] ⚠️ Disabled in release builds")
            return
        }
        if (transport != null) return
        transport = BridgeTransport(serverUrl, registry, authToken)
        transport?.connect()
    }

    fun stop() {
        transport?.close()
        transport = null
    }

    /**
     * Attaches Overlay to Activity (called from onResume)
     */
    fun attachOverlay(activity: Activity) {
        BridgeOverlayManager.attach(activity)
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
    ): Boolean {
        val escapedTree = treeJson.replace("\"", "\\\"")
        val json = """
            {"type":"analyze_element_with_tree","file":"$file","line":$line,"offset":$utf16Offset,"length":$utf16Length,"tree":"$escapedTree","request_id":$requestId}
        """.trimIndent()
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
}
