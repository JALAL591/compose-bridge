/**
 * ComposeBridge APK Delivery State.
 * إدارة حالة بناء واستلام وتثبيت حزم الـ APK عبر التحديث الهوائي (OTA).
 */
package com.composebridge.agent.state

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

object ApkDeliveryState {
    var showApkBuildDialog: Boolean by mutableStateOf(false)
    var isBuildingApk: Boolean by mutableStateOf(false)
    var apkBuildStage: String by mutableStateOf("idle") // "building", "sending", "installing", "error"
    var apkBuildProgress: Float by mutableStateOf(0.0f)
    var apkBuildMessage: String by mutableStateOf("")
    var apkAvailableFileName: String by mutableStateOf("")
    var apkAvailableFileSize: String by mutableStateOf("")
    var apkAvailableTimeAgo: String by mutableStateOf("")
}

