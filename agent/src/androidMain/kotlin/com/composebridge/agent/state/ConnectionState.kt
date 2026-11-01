/**
 * ComposeBridge Connection State.
 * إدارة حالة الاتصال بالخادم (Connected, Reconnecting, Disconnected) ونوافذ الاتصال عن بعد.
 */
package com.composebridge.agent.state

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

object ConnectionState {
    var isConnected: Boolean by mutableStateOf(false)
    var isReconnecting: Boolean by mutableStateOf(false)
    var connectionStatusText: String by mutableStateOf("Disconnected")
    var showRemoteDialog: Boolean by mutableStateOf(false)
}

