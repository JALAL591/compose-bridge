package com.composebridge.plugin.services

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.codeInsight.daemon.impl.DaemonCodeAnalyzerImpl
import com.intellij.codeInsight.daemon.impl.HighlightInfo
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.ReadAction
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.editor.Document
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.fileEditor.FileEditor
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.io.File
import java.net.URI
import java.net.http.HttpClient
import java.net.http.WebSocket
import java.util.concurrent.CompletionStage
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume

/**
 * Event-Driven Real-time IDE Compilation & Syntax Diagnostics Service.
 * Listens to DaemonCodeAnalyzer.DAEMON_EVENT_TOPIC for instant error resolution without fixed delays or Gradle builds.
 */
object IdeDiagnosticsService {
    private val LOG = Logger.getInstance(IdeDiagnosticsService::class.java)
    private val gson = Gson()
    private val scope = CoroutineScope(Dispatchers.Default)

    @Volatile
    private var activeWebSocket: WebSocket? = null
    private val isConnecting = AtomicBoolean(false)

    data class DiagnosticItem(
        val line: Int,
        val column: Int,
        val severity: String,
        val message: String,
        val inspectionId: String = ""
    )

    data class DiagnosticsResult(
        val success: Boolean,
        val file: String,
        val errorsCount: Int,
        val warningsCount: Int,
        val items: List<DiagnosticItem>,
        val error: String? = null
    )

    /**
     * Listens for the DaemonCodeAnalyzer to finish analyzing the current file.
     * Replaces fixed timeouts with reactive event-driven synchronization.
     */
    suspend fun awaitDaemonFinished(project: Project, maxTimeoutMs: Long = 1000): Boolean {
        return withTimeoutOrNull(maxTimeoutMs) {
            suspendCancellableCoroutine { continuation ->
                val connection = project.messageBus.connect()
                connection.subscribe(
                    DaemonCodeAnalyzer.DAEMON_EVENT_TOPIC,
                    object : DaemonCodeAnalyzer.DaemonListener {
                        override fun daemonFinished(fileEditors: Collection<FileEditor>) {
                            connection.disconnect()
                            if (continuation.isActive) {
                                continuation.resume(true)
                            }
                        }
                    }
                )
                continuation.invokeOnCancellation {
                    connection.disconnect()
                }
            }
        } ?: false
    }

    /**
     * Surgically extracts code highlights (errors & warnings) for a target file or active editor.
     * Reactively waits for the analysis daemon before reading the AST highlights.
     */
    suspend fun collectDiagnostics(
        project: Project,
        targetFilePath: String? = null,
        includeWarnings: Boolean = false
    ): DiagnosticsResult {
        val fdm = FileDocumentManager.getInstance()
        val fem = FileEditorManager.getInstance(project)

        val (doc, vFile) = ApplicationManager.getApplication().runReadAction<Pair<Document?, VirtualFile?>> {
            var d: Document? = null
            var vf: VirtualFile? = null

            // 1. Explicit target path if provided
            if (!targetFilePath.isNullOrBlank()) {
                val candidateFile = if (File(targetFilePath).isAbsolute) {
                    File(targetFilePath)
                } else {
                    File(project.basePath ?: ".", targetFilePath)
                }
                vf = LocalFileSystem.getInstance().findFileByIoFile(candidateFile)
                if (vf != null) {
                    d = fdm.getDocument(vf)
                }
            }

            // 2. Selected file in editor tabs (works even when Tool Window has focus)
            if (d == null || vf == null) {
                val selectedFile = fem.selectedFiles.firstOrNull()
                if (selectedFile != null) {
                    vf = selectedFile
                    d = fdm.getDocument(selectedFile)
                }
            }

            // 3. Active text editor if available
            if (d == null || vf == null) {
                val selectedEditor = fem.selectedTextEditor
                if (selectedEditor != null) {
                    d = selectedEditor.document
                    vf = fdm.getFile(d)
                }
            }

            // 4. Any open file in editor tabs as fallback
            if (d == null || vf == null) {
                val openFile = fem.openFiles.firstOrNull()
                if (openFile != null) {
                    vf = openFile
                    d = fdm.getDocument(openFile)
                }
            }

            Pair(d, vf)
        }

        // If no file is open anywhere in editor, return graceful status immediately
        if (doc == null || vFile == null) {
            return DiagnosticsResult(
                success = false,
                file = targetFilePath ?: "",
                errorsCount = 0,
                warningsCount = 0,
                items = emptyList(),
                error = "No file currently open in editor. Open a Kotlin file to view diagnostics."
            )
        }

        // Step 1: Wait for daemon analysis to finish on the resolved file
        val daemonReady = awaitDaemonFinished(project, 1500L)
        if (!daemonReady) {
            LOG.debug("Daemon analysis timeout (1500ms reached); reading latest available stable state.")
        }

        val finalDoc = doc
        val finalVFile = vFile

        return try {
            val minSeverity = if (includeWarnings) HighlightSeverity.INFORMATION else HighlightSeverity.ERROR
            var rawHighlights = ApplicationManager.getApplication().runReadAction<List<HighlightInfo>> {
                DaemonCodeAnalyzerImpl.getHighlights(finalDoc, minSeverity, project)
            }

            if (rawHighlights.isEmpty()) {
                val daemon = DaemonCodeAnalyzer.getInstance(project) as? DaemonCodeAnalyzerImpl
                val psiFile = ApplicationManager.getApplication().runReadAction<com.intellij.psi.PsiFile?> {
                    com.intellij.psi.PsiManager.getInstance(project).findFile(finalVFile)
                }
                if (daemon != null && psiFile != null) {
                    try {
                        val daemonIndicator = com.intellij.codeInsight.daemon.impl.DaemonProgressIndicator()
                        rawHighlights = com.intellij.openapi.progress.ProgressManager.getInstance().runProcess(
                            com.intellij.openapi.util.Computable {
                                daemon.runMainPasses(psiFile, finalDoc, daemonIndicator)
                            },
                            daemonIndicator
                        )
                    } catch (_: Exception) {}
                }
            }

            val items = ReadAction.nonBlocking<List<DiagnosticItem>> {
                rawHighlights.filter { info ->
                    if (includeWarnings) {
                        info.severity >= HighlightSeverity.INFORMATION &&
                        (!info.description.isNullOrBlank() || !info.toolTip.isNullOrBlank())
                    } else {
                        info.severity >= HighlightSeverity.ERROR
                    }
                }.map { info ->
                    val line = try {
                        finalDoc.getLineNumber(info.actualStartOffset) + 1
                    } catch (_: Exception) {
                        1
                    }

                    val col = try {
                        val lineStart = finalDoc.getLineStartOffset(line - 1)
                        (info.actualStartOffset - lineStart) + 1
                    } catch (_: Exception) {
                        1
                    }

                    val sevName = when (info.severity) {
                        HighlightSeverity.ERROR -> "ERROR"
                        HighlightSeverity.WARNING -> "WARNING"
                        HighlightSeverity.WEAK_WARNING -> "WEAK_WARNING"
                        HighlightSeverity.INFORMATION, HighlightSeverity.INFO -> "INFO"
                        else -> if (info.severity >= HighlightSeverity.ERROR) "ERROR"
                                else if (info.severity >= HighlightSeverity.WARNING) "WARNING"
                                else if (info.severity >= HighlightSeverity.WEAK_WARNING) "WEAK_WARNING"
                                else "INFO"
                    }

                    val rawMsg = info.description ?: info.toolTip ?: "Diagnostic finding"
                    val cleanMsg = rawMsg.replace(Regex("<[^>]*>"), "").replace("&nbsp;", " ").trim()

                    val inspId = info.inspectionToolId ?: run {
                        val words = cleanMsg.split(" ").take(3).joinToString(" ")
                        if (words.isNotBlank()) words else "General"
                    }

                    DiagnosticItem(
                        line = line,
                        column = col,
                        severity = sevName,
                        message = cleanMsg,
                        inspectionId = inspId
                    )
                }
            }.executeSynchronously()

            val errCount = items.count { it.severity == "ERROR" }
            val warnCount = items.count { it.severity == "WARNING" || it.severity == "WEAK_WARNING" || it.severity != "ERROR" }

            val result = DiagnosticsResult(
                success = true,
                file = finalVFile.name,
                errorsCount = errCount,
                warningsCount = warnCount,
                items = items
            )

            // Cache to disk
            saveDiagnosticsToState(project, result)
            result
        } catch (e: Exception) {
            LOG.warn("Failed to collect IDE diagnostics: ${e.message}")
            DiagnosticsResult(
                success = false,
                file = finalVFile.name,
                errorsCount = 0,
                warningsCount = 0,
                items = emptyList(),
                error = e.message ?: "Unknown DaemonCodeAnalyzer error"
            )
        }
    }

    /**
     * Synchronous blocking wrapper for non-coroutine callers.
     */
    fun collectDiagnosticsBlocking(
        project: Project,
        targetFilePath: String? = null,
        includeWarnings: Boolean = false
    ): DiagnosticsResult = runBlocking {
        collectDiagnostics(project, targetFilePath, includeWarnings)
    }

    /**
     * Persists latest diagnostics into .composebridge-state/ide_diagnostics.json
     */
    fun saveDiagnosticsToState(project: Project, result: DiagnosticsResult) {
        try {
            val root = project.basePath ?: return
            val stateDir = File(root, ".composebridge-state")
            if (!stateDir.exists()) stateDir.mkdirs()
            val file = File(stateDir, "ide_diagnostics.json")
            file.writeText(gson.toJson(result), Charsets.UTF_8)
        } catch (_: Exception) {
        }
    }

    /**
     * Starts background WebSocket listener connected to ComposeBridge server (ws://127.0.0.1:8711).
     */
    fun ensureConnected(project: Project, serverUri: String = "ws://127.0.0.1:8711") {
        if (activeWebSocket != null) return
        if (!isConnecting.compareAndSet(false, true)) return

        val token = BridgeServerManager.readAuthToken(project.basePath)
        val client = HttpClient.newHttpClient()

        try {
            client.newWebSocketBuilder()
                .buildAsync(URI.create(serverUri), object : WebSocket.Listener {
                    override fun onOpen(webSocket: WebSocket) {
                        activeWebSocket = webSocket
                        isConnecting.set(false)
                        LOG.info("IdeDiagnosticsService connected to Bridge server")
                        webSocket.sendText(gson.toJson(mapOf("type" to "auth", "token" to token)), true)
                        webSocket.request(1)
                    }

                    override fun onText(webSocket: WebSocket, data: CharSequence, last: Boolean): CompletionStage<*>? {
                        try {
                            val text = data.toString()
                            val obj = JsonParser.parseString(text).asJsonObject
                            val msgType = obj.get("type")?.asString

                            if (msgType == "ide_diagnostics_request") {
                                val reqId = obj.get("request_id")?.asString ?: ""
                                val targetFile = obj.get("file")?.asString
                                val includeWarnings = obj.get("include_warnings")?.asBoolean ?: false

                                // Step 1 & 2: Event-driven wait via Coroutine Scope
                                scope.launch {
                                    val res = collectDiagnostics(project, targetFile, includeWarnings)
                                    val response = JsonObject().apply {
                                        addProperty("type", "ide_diagnostics_response")
                                        addProperty("request_id", reqId)
                                        addProperty("success", res.success)
                                        addProperty("file", res.file)
                                        addProperty("errors_count", res.errorsCount)
                                        addProperty("warnings_count", res.warningsCount)
                                        add("diagnostics", gson.toJsonTree(res.items))
                                        if (res.error != null) {
                                            addProperty("error", res.error)
                                        }
                                    }
                                    webSocket.sendText(gson.toJson(response), true)
                                }
                            }

                            if (msgType == "project_diagnostics_scan_request") {
                                val reqId = obj.get("request_id")?.asString ?: ""
                                val includeWarnings = obj.get("include_warnings")?.asBoolean ?: false
                                val maxFiles = obj.get("max_files")?.asInt ?: 100

                                scope.launch {
                                    val scanReport = ProjectDiagnosticsScanner.scanProject(
                                        project = project,
                                        includeWarnings = includeWarnings,
                                        maxFiles = maxFiles
                                    )
                                    val response = JsonObject().apply {
                                        addProperty("type", "project_diagnostics_scan_response")
                                        addProperty("request_id", reqId)
                                        addProperty("success", scanReport.success)
                                        addProperty("scanned_files_count", scanReport.scannedFilesCount)
                                        addProperty("total_errors", scanReport.totalErrors)
                                        addProperty("total_warnings", scanReport.totalWarnings)
                                        addProperty("files_with_issues_count", scanReport.filesWithIssuesCount)
                                        add("files", gson.toJsonTree(scanReport.files))
                                        if (scanReport.error != null) {
                                            addProperty("error", scanReport.error)
                                        }
                                    }
                                    webSocket.sendText(gson.toJson(response), true)
                                }
                            }
                        } catch (e: Exception) {
                            LOG.warn("Error processing diagnostics message: ${e.message}")
                        }
                        webSocket.request(1)
                        return null
                    }

                    override fun onClose(webSocket: WebSocket, statusCode: Int, reason: String): CompletionStage<*>? {
                        activeWebSocket = null
                        isConnecting.set(false)
                        return null
                    }

                    override fun onError(webSocket: WebSocket, error: Throwable) {
                        activeWebSocket = null
                        isConnecting.set(false)
                    }
                })
        } catch (e: Exception) {
            isConnecting.set(false)
            LOG.warn("Failed to initiate WebSocket connection: ${e.message}")
        }
    }

    fun sendWebSocketMessage(payload: JsonObject): Boolean {
        val ws = activeWebSocket ?: return false
        return try {
            ws.sendText(gson.toJson(payload), true)
            true
        } catch (_: Exception) {
            false
        }
    }

    fun disconnect() {
        try {
            activeWebSocket?.sendClose(WebSocket.NORMAL_CLOSURE, "Plugin disconnect")
        } catch (_: Exception) {
        }
        activeWebSocket = null
        isConnecting.set(false)
    }
}
