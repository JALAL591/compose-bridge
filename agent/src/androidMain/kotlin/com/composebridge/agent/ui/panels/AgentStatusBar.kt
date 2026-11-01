/**
 * ComposeBridge Agent Status Bar.
 * شريط حالة خادم وكيل ComposeBridge الذي يعرض حالة الاتصال ومزامنة التعديلات.
 */
package com.composebridge.agent.ui.panels

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.composebridge.agent.BridgeState
import com.composebridge.agent.ComposeBridgeAgent

/**
 * شريط عرض حالة الاتصال وحالة الوكيل وسلسلة التعديلات المعلقة للمزامنة.
 * Agent status bar displaying connection status, agent activity, and pending edits.
 */
@Composable
fun AgentStatusBar() {
    val agentBusy = BridgeState.agentBusy
    val queueCount = BridgeState.queueCount
    val isConnected = BridgeState.isConnected
    val isReconnecting = BridgeState.isReconnecting

    LaunchedEffect(Unit) {
        ComposeBridgeAgent.requestQueueStatus()
    }

    val statusBg = when {
        isReconnecting -> Color(0xFFFFF8E1)
        !isConnected -> Color(0xFFFFEBEE)
        agentBusy -> Color(0xFFFFF3E0)
        else -> Color(0xFFE8F5E9)
    }

    val statusText = when {
        isReconnecting -> "🔄 Reconnecting..."
        !isConnected -> "🔴 Disconnected"
        agentBusy -> "🤖 Agent busy..."
        else -> "🟢 Bridge Running"
    }

    val statusColor = when {
        isReconnecting -> Color(0xFFF59E0B)
        !isConnected -> Color(0xFFEF4444)
        agentBusy -> Color(0xFFE65100)
        else -> Color(0xFF2E7D32)
    }

    Surface(
        color = statusBg,
        shape = RoundedCornerShape(8.dp),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column {
                Text(
                    text = statusText,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold,
                    color = statusColor
                )
                if (queueCount > 0) {
                    Text(
                        text = "📥 $queueCount pending edit(s)",
                        fontSize = 12.sp,
                        color = Color(0xFF616161)
                    )
                }
            }

            if (queueCount > 0) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = {
                            ComposeBridgeAgent.requestQueueClear()
                        },
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                    ) {
                        Text("🗑️", fontSize = 12.sp)
                    }
                    val syncing = BridgeState.syncing
                    Button(
                        onClick = {
                            BridgeState.setSyncing(true)
                            ComposeBridgeAgent.requestUserSync()
                        },
                        enabled = !syncing,
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp)
                    ) {
                        if (syncing) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(12.dp),
                                    strokeWidth = 2.dp,
                                    color = Color.White
                                )
                                Text("Syncing...", fontSize = 12.sp)
                            }
                        } else {
                            Text("🔄 Sync", fontSize = 12.sp)
                        }
                    }
                }
            }
        }
    }

    Spacer(Modifier.height(12.dp))
}

