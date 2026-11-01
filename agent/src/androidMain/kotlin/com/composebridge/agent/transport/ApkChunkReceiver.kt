/**
 * ComposeBridge APK Chunk Receiver.
 * استقبال وتجميع حزم ملف الـ APK وتثبيته عبر التحديث الهوائي (OTA).
 */
package com.composebridge.agent.transport

import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.provider.MediaStore
import android.util.Base64
import android.util.Log
import androidx.core.content.FileProvider
import com.composebridge.agent.BridgeBackgroundService
import com.composebridge.agent.BridgeState
import com.composebridge.agent.ComposeBridgeFileProvider
import kotlinx.serialization.json.*
import okhttp3.WebSocket
import java.io.File
import java.io.FileOutputStream

class ApkChunkReceiver {
    companion object {
        private const val TAG = "ComposeBridge"
        private const val PREFS_NAME = "composebridge_prefs"
        private const val KEY_LAST_APK_CHUNK = "composebridge_last_apk_chunk"
        private const val KEY_APK_IN_PROGRESS = "composebridge_apk_in_progress"
        private const val KEY_TOTAL_CHUNKS = "composebridge_total_chunks"
        private const val KEY_APK_FILE_NAME = "composebridge_apk_file_name"
    }

    @Volatile var apkOutputFile: File? = null
    @Volatile var apkOutputStream: FileOutputStream? = null
    @Volatile var apkReceivedChunks = 0
    @Volatile var lastNotifiedProgress = 0

    fun handleApkMessage(type: String, obj: JsonObject, text: String, context: Context?): Boolean {
        if (type == "apk_available") {
            val fileName = obj["file_name"]?.jsonPrimitive?.contentOrNull ?: "debug.apk"
            val fileSize = obj["file_size_str"]?.jsonPrimitive?.contentOrNull ?: ""
            val timeAgo = obj["time_ago"]?.jsonPrimitive?.contentOrNull ?: ""
            BridgeState.isBuildingApk = false
            BridgeState.apkBuildStage = "apk_available"
            BridgeState.apkAvailableFileName = fileName
            BridgeState.apkAvailableFileSize = fileSize
            BridgeState.apkAvailableTimeAgo = timeAgo
            BridgeState.apkBuildMessage = "Pre-built APK is ready on server for instant transfer."
            return true
        }

        if (type == "apk_build_status_response") {
            val building = obj["building"]?.jsonPrimitive?.booleanOrNull ?: false
            val stage = obj["stage"]?.jsonPrimitive?.contentOrNull ?: "idle"
            val progress = obj["progress"]?.jsonPrimitive?.contentOrNull?.toFloatOrNull() ?: 0f
            val message = obj["message"]?.jsonPrimitive?.contentOrNull ?: ""
            BridgeState.isBuildingApk = building
            if (building) {
                BridgeState.apkBuildStage = stage
                BridgeState.apkBuildProgress = progress
                BridgeState.apkBuildMessage = message
            } else if (BridgeState.apkBuildStage == "building" && !building) {
                BridgeState.apkBuildStage = stage
                BridgeState.apkBuildMessage = message
            }
            return true
        }

        if (type == "apk_build_progress") {
            Log.d(TAG, "📦 [BridgeTransport] Received apk_build_progress: $text")
            val stage = obj["stage"]?.jsonPrimitive?.contentOrNull ?: "building"
            val message = obj["message"]?.jsonPrimitive?.contentOrNull ?: ""
            val progress = obj["progress"]?.jsonPrimitive?.contentOrNull?.toFloatOrNull() ?: 0.0f
            BridgeState.isBuildingApk = true
            BridgeState.apkBuildStage = stage
            BridgeState.apkBuildMessage = message
            BridgeState.apkBuildProgress = progress
            context?.let { ctx ->
                BridgeBackgroundService.updateBuildProgress(ctx, (progress * 100).toInt(), message)
            }
            return true
        }

        if (type == "apk_build_error") {
            Log.e(TAG, "❌ [BridgeTransport] Received apk_build_error: $text")
            val message = obj["message"]?.jsonPrimitive?.contentOrNull ?: "Unknown build error"
            BridgeState.isBuildingApk = false
            BridgeState.apkBuildStage = "error"
            BridgeState.apkBuildMessage = message
            return true
        }

        if (type == "apk_chunk") {
            val chunkIndex = obj["chunk_index"]?.jsonPrimitive?.intOrNull ?: 0
            val totalChunks = obj["total_chunks"]?.jsonPrimitive?.intOrNull ?: 1
            val dataBase64 = obj["data"]?.jsonPrimitive?.contentOrNull ?: ""
            val fileName = obj["file_name"]?.jsonPrimitive?.contentOrNull ?: "composeApp-debug.apk"

            val ctx = context

            if (chunkIndex == 1 || (chunkIndex == 0 && apkOutputStream == null)) {
                Log.d(TAG, "📦 [BridgeTransport] Starting fresh APK download on device...")
                if (ctx != null) {
                    try {
                        val apkFile = File(ctx.cacheDir, "composebridge_update.apk")
                        if (apkFile.exists()) apkFile.delete()
                        apkOutputFile = apkFile
                        apkOutputStream = FileOutputStream(apkFile, false)
                        apkReceivedChunks = 0
                        lastNotifiedProgress = 0
                        ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit()
                            .putBoolean(KEY_APK_IN_PROGRESS, true)
                            .putInt(KEY_LAST_APK_CHUNK, 0)
                            .putInt(KEY_TOTAL_CHUNKS, totalChunks)
                            .putString(KEY_APK_FILE_NAME, fileName)
                            .apply()
                    } catch (e: Exception) {
                        Log.e(TAG, "Failed to create APK file in cache", e)
                    }
                }
            } else if (apkOutputStream == null && ctx != null) {
                // Resumed download: open stream in append mode
                try {
                    val apkFile = File(ctx.cacheDir, "composebridge_update.apk")
                    apkOutputFile = apkFile
                    apkOutputStream = FileOutputStream(apkFile, true)
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to open APK file for appending", e)
                }
            }

            if (dataBase64.isNotEmpty() && apkOutputStream != null) {
                try {
                    val bytes = Base64.decode(dataBase64, Base64.DEFAULT)
                    apkOutputStream?.write(bytes)
                    apkReceivedChunks = chunkIndex

                    // Save last received chunk index in SharedPreferences
                    ctx?.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)?.edit()
                        ?.putBoolean(KEY_APK_IN_PROGRESS, true)
                        ?.putInt(KEY_LAST_APK_CHUNK, chunkIndex)
                        ?.putInt(KEY_TOTAL_CHUNKS, totalChunks)
                        ?.putString(KEY_APK_FILE_NAME, fileName)
                        ?.apply()
                } catch (e: Exception) {
                    Log.e(TAG, "Error writing APK chunk $chunkIndex", e)
                }
            }

            val chunkProg = chunkIndex.toFloat() / totalChunks.toFloat().coerceAtLeast(1f)
            val pct = (chunkProg * 100).toInt()

            BridgeState.apkBuildStage = "sending"
            BridgeState.apkBuildMessage = "Receiving APK: $pct% ($chunkIndex/$totalChunks)"
            BridgeState.apkBuildProgress = chunkProg

            // Throttling: only update notification every 5% or on boundary chunks
            if (ctx != null && (pct - lastNotifiedProgress >= 5 || chunkIndex == totalChunks || chunkIndex == 1)) {
                lastNotifiedProgress = pct
                BridgeBackgroundService.updateBuildProgress(ctx, pct, "Downloading APK: $pct%")
            }
            return true
        }

        if (type == "apk_complete") {
            Log.d(TAG, "📦 [BridgeTransport] Received apk_complete from server! Preparing installer...")
            try {
                apkOutputStream?.flush()
                apkOutputStream?.close()
            } catch (e: Exception) {
                Log.e(TAG, "Error closing APK stream", e)
            }
            apkOutputStream = null
            lastNotifiedProgress = 0

            val ctx = context
            // Clear download flags in SharedPreferences
            ctx?.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)?.edit()
                ?.putBoolean(KEY_APK_IN_PROGRESS, false)
                ?.putInt(KEY_LAST_APK_CHUNK, 0)
                ?.apply()

            val apkFile = apkOutputFile ?: ctx?.let { File(it.cacheDir, "composebridge_update.apk") }
            if (apkFile != null && apkFile.exists() && apkFile.length() > 0) {
                BridgeState.apkBuildStage = "installing"
                BridgeState.apkBuildMessage = "APK ready (${apkFile.length() / 1024} KB). Launching installer..."
                BridgeState.apkBuildProgress = 1.0f
                BridgeState.isBuildingApk = false

                if (ctx != null) {
                    installApk(ctx, apkFile)
                } else {
                    BridgeState.apkBuildStage = "error"
                    BridgeState.apkBuildMessage = "App context not available to launch installer"
                }
            } else {
                BridgeState.apkBuildStage = "error"
                BridgeState.apkBuildMessage = "APK file is empty or missing"
                BridgeState.isBuildingApk = false
            }
            return true
        }

        return false
    }

    fun checkAndResumeApkDownload(webSocket: WebSocket, context: Context?, mainHandler: Handler) {
        val ctx = context ?: return
        try {
            val prefs = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            val inProgress = prefs.getBoolean(KEY_APK_IN_PROGRESS, false)
            val lastChunk = prefs.getInt(KEY_LAST_APK_CHUNK, 0)
            val fileName = prefs.getString(KEY_APK_FILE_NAME, "") ?: ""
            val apkFile = File(ctx.cacheDir, "composebridge_update.apk")

            if (inProgress && lastChunk > 0 && apkFile.exists() && apkFile.length() > 0) {
                Log.d(TAG, "🔄 [BridgeTransport] Found incomplete APK download (lastChunk=$lastChunk, size=${apkFile.length()} bytes). Requesting resume...")
                mainHandler.post {
                    BridgeState.isBuildingApk = true
                    BridgeState.apkBuildStage = "sending"
                    BridgeState.apkBuildMessage = "Resuming APK download from chunk $lastChunk..."
                }
                apkOutputFile = apkFile
                apkOutputStream = FileOutputStream(apkFile, true)
                apkReceivedChunks = lastChunk

                val payload = """{"type":"resume_apk","last_chunk":$lastChunk,"file_name":"$fileName"}"""
                webSocket.send(payload)
            }
        } catch (e: Exception) {
            Log.w(TAG, "Error checking for resumable APK download", e)
        }
    }

    fun saveApkToDownloads(context: Context, sourceFile: File, displayName: String = "ComposeBridge-Update.apk"): Uri? {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, displayName)
                    put(MediaStore.MediaColumns.MIME_TYPE, "application/vnd.android.package-archive")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/ComposeBridge")
                    put(MediaStore.MediaColumns.IS_PENDING, 1)
                }
                val resolver = context.contentResolver
                val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                if (uri != null) {
                    resolver.openOutputStream(uri)?.use { out ->
                        sourceFile.inputStream().use { input ->
                            input.copyTo(out)
                        }
                    }
                    values.clear()
                    values.put(MediaStore.MediaColumns.IS_PENDING, 0)
                    resolver.update(uri, values, null, null)
                    Log.d(TAG, "💾 Saved APK to Downloads via MediaStore: $uri")
                    return uri
                }
            } else {
                val downloadsDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "ComposeBridge")
                if (!downloadsDir.exists()) downloadsDir.mkdirs()
                val destFile = File(downloadsDir, displayName)
                sourceFile.copyTo(destFile, overwrite = true)
                Log.d(TAG, "💾 Saved APK to Downloads directory: ${destFile.absolutePath}")
                val authority = "${context.packageName}.composebridge.provider"
                return try {
                    ComposeBridgeFileProvider.getUriForFile(context, authority, destFile)
                } catch (_: Exception) {
                    Uri.fromFile(destFile)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to save APK to Downloads", e)
        }
        return null
    }

    fun installApk(context: Context, apkFile: File) {
        try {
            val savedUri = saveApkToDownloads(context, apkFile, "ComposeBridge-Update.apk")
            val authority = "${context.packageName}.composebridge.provider"
            val contentUri = savedUri ?: try {
                ComposeBridgeFileProvider.getUriForFile(context, authority, apkFile)
            } catch (e: Exception) {
                try {
                    FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", apkFile)
                } catch (e2: Exception) {
                    FileProvider.getUriForFile(context, "${context.packageName}.provider", apkFile)
                }
            }

            BridgeBackgroundService.showApkDownloadedNotification(context, contentUri, "ComposeBridge-Update.apk")

            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(contentUri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to launch package installer", e)
            BridgeState.apkBuildStage = "error"
            BridgeState.apkBuildMessage = "Install launch failed: ${e.message}"
        }
    }
}
