/**
 * ComposeBridge Preference Helper.
 * إدارة وتوحيد مفاتيح وإعدادات SharedPreferences في الـ Agent.
 */
package com.composebridge.agent.util

import android.content.Context
import android.content.SharedPreferences

object PreferenceHelper {
    const val PREFS_NAME = "composebridge_prefs"

    // Auth & Network Keys
    const val KEY_AUTH_TOKEN = "composebridge_auth_token"
    const val KEY_REMOTE_URL = "composebridge_remote_url"
    const val KEY_LOCAL_URL = "composebridge_local_url"
    const val KEY_IS_REMOTE = "composebridge_is_remote"

    // OTA APK Keys
    const val KEY_LAST_APK_CHUNK = "composebridge_last_apk_chunk"
    const val KEY_APK_IN_PROGRESS = "composebridge_apk_in_progress"
    const val KEY_TOTAL_CHUNKS = "composebridge_total_chunks"
    const val KEY_APK_FILE_NAME = "composebridge_apk_file_name"

    fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun getAuthToken(context: Context): String {
        return getPrefs(context).getString(KEY_AUTH_TOKEN, "") ?: ""
    }

    fun setAuthToken(context: Context, token: String) {
        getPrefs(context).edit().putString(KEY_AUTH_TOKEN, token).apply()
    }
}

