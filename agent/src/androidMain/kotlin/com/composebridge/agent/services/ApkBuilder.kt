/**
 * ComposeBridge APK Builder Service.
 * إدارة طلبات بناء حزم التطبيق OTA عبر Gradle والتحقق من حالتها وجلبها.
 */
package com.composebridge.agent.services

import android.util.Log
import com.composebridge.agent.BridgeState
import com.composebridge.agent.BridgeTransport

object ApkBuilder {
    private const val TAG = "ComposeBridge"

    fun buildAndSendApk(transport: BridgeTransport?, forceRebuild: Boolean = false): Boolean {
        Log.d(TAG, "📦 [ApkBuilder] buildAndSendApk(forceRebuild=$forceRebuild) called")
        BridgeState.isBuildingApk = true
        BridgeState.apkBuildStage = "building"
        BridgeState.apkBuildMessage = "Starting Gradle build (assembleDebug)..."
        BridgeState.apkBuildProgress = 0.05f

        val payload = if (forceRebuild) {
            """{"type":"build_and_send_apk","force_rebuild":true}"""
        } else {
            """{"type":"build_and_send_apk"}"""
        }

        if (transport == null) {
            Log.e(TAG, "❌ [ApkBuilder] transport is NULL! Cannot send build_and_send_apk.")
            BridgeState.isBuildingApk = false
            BridgeState.apkBuildStage = "error"
            BridgeState.apkBuildMessage = "Transport is not connected to server"
            return false
        }
        val sent = transport.send(payload)
        Log.d(TAG, "📦 [ApkBuilder] buildAndSendApk() sent result: $sent")
        return sent
    }

    fun fetchExistingApk(transport: BridgeTransport?): Boolean {
        BridgeState.isBuildingApk = true
        BridgeState.apkBuildStage = "sending"
        BridgeState.apkBuildMessage = "Requesting existing APK from server..."
        BridgeState.apkBuildProgress = 0.1f
        return transport?.send("""{"type":"fetch_existing_apk"}""") ?: false
    }

    fun requestApkBuildStatus(transport: BridgeTransport?): Boolean {
        return transport?.send("""{"type":"get_apk_build_status"}""") ?: false
    }
}

