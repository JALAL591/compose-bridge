package com.composebridge.agent

import android.app.Activity
import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog

@Composable
fun RemoteConnectionDialog(
    onDismissRequest: () -> Unit
) {
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current

    var isRemoteMode by remember {
        mutableStateOf(ComposeBridgeAgent.isRemoteMode(context))
    }

    val savedRemote = remember { ComposeBridgeAgent.getSavedRemoteUrl(context) }
    var remoteUrl by remember { mutableStateOf(if (savedRemote.isNotBlank()) savedRemote else "wss://") }

    var token by remember {
        mutableStateOf(
            context.getSharedPreferences("composebridge_prefs", android.content.Context.MODE_PRIVATE)
                .getString("composebridge_auth_token", "") ?: ""
        )
    }

    val activeUrl = ComposeBridgeAgent.getActiveUrl(context)

    Dialog(onDismissRequest = onDismissRequest) {
        Card(
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = Color(0xFF1E293B)),
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
                .border(1.dp, Color(0x33FFFFFF), RoundedCornerShape(16.dp))
        ) {
            Column(
                modifier = Modifier
                    .padding(20.dp)
                    .fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "🌐 Connection Settings (Bridge)",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    IconButton(onClick = onDismissRequest) {
                        Text(text = "✕", color = Color(0xFF94A3B8), fontSize = 16.sp)
                    }
                }

                // Mode Selector Toggle (Local vs Remote)
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(10.dp))
                        .background(Color(0xFF0F172A))
                        .padding(4.dp),
                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    // Local Button
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (!isRemoteMode) Color(0xFF3B82F6) else Color.Transparent)
                            .clickable {
                                isRemoteMode = false
                                ComposeBridgeAgent.resetToLocal(context)
                            }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "🔌 Local (127.0.0.1)",
                            color = Color.White,
                            fontWeight = if (!isRemoteMode) FontWeight.Bold else FontWeight.Normal,
                            fontSize = 13.sp
                        )
                    }

                    // Remote Button
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(8.dp))
                            .background(if (isRemoteMode) Color(0xFF10B981) else Color.Transparent)
                            .clickable {
                                // إيقاف أي محاولة إعادة اتصال محلي قبل التبديل
                                ComposeBridgeAgent.disconnect()
                                isRemoteMode = true
                            }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "🌍 Remote",
                            color = Color.White,
                            fontWeight = if (isRemoteMode) FontWeight.Bold else FontWeight.Normal,
                            fontSize = 13.sp
                        )
                    }
                }

                // Connection status banner
                val isConnected = BridgeState.isConnected
                val statusText = BridgeState.connectionStatusText
                Surface(
                    color = if (isConnected) Color(0x2210B981) else Color(0x22EF4444),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(if (isConnected) "🟢" else "🔴")
                            Text(
                                text = "Status: $statusText",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = if (isConnected) Color(0xFF34D399) else Color(0xFFF87171)
                            )
                        }
                        Text(
                            text = "Active URL: $activeUrl",
                            fontSize = 11.sp,
                            color = Color(0xFF94A3B8)
                        )
                    }
                }

                if (isRemoteMode) {
                    // QR Code scan / Paste button
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = {
                                try {
                                    val activity = context as? Activity
                                    if (activity != null) {
                                        val currentPkg = context.packageName
                                        val scannerClass = try {
                                            Class.forName("$currentPkg.ui.QrScannerActivity")
                                        } catch (_: Exception) {
                                            Class.forName("com.edu.teacher.ui.QrScannerActivity")
                                        }
                                        val intent = Intent(activity, scannerClass)
                                        activity.startActivity(intent)
                                        onDismissRequest()
                                    }
                                } catch (_: Exception) {
                                    BridgeState.showSnackbar("Could not open camera - please paste from clipboard")
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF6366F1)),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("📷 Scan QR", color = Color.White, fontSize = 13.sp)
                        }

                        Button(
                            onClick = {
                                val clip = clipboardManager.getText()?.text ?: ""
                                if (clip.isNotBlank()) {
                                    val applied = ComposeBridgeAgent.applyQrPayload(context, clip)
                                    if (applied) {
                                        BridgeState.showSnackbar("✅ Connection settings imported successfully!")
                                        onDismissRequest()
                                        return@Button
                                    }
                                }
                                BridgeState.showSnackbar("⚠️ Clipboard does not contain valid connection JSON")
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF3B82F6)),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text("📋 Paste from Clipboard", color = Color.White, fontSize = 13.sp)
                        }
                    }

                    // Remote URL Input
                    OutlinedTextField(
                        value = remoteUrl,
                        onValueChange = { remoteUrl = it },
                        label = { Text("Remote WebSocket URL (wss://...)") },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF38BDF8),
                            unfocusedBorderColor = Color(0xFF475569)
                        ),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )

                    // Auth Token Input
                    OutlinedTextField(
                        value = token,
                        onValueChange = { token = it },
                        label = { Text("Dynamic Auth Token (64-hex)") },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedBorderColor = Color(0xFF38BDF8),
                            unfocusedBorderColor = Color(0xFF475569)
                        ),
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )

                    // Connect button
                    Button(
                        onClick = {
                            if (remoteUrl.isNotBlank() && remoteUrl != "wss://") {
                                ComposeBridgeAgent.connectRemote(context, remoteUrl, token)
                                onDismissRequest()
                            } else {
                                BridgeState.showSnackbar("⚠️ Please enter a valid wss:// URL")
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF10B981)),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Connect Remote", color = Color.White, fontWeight = FontWeight.Bold)
                    }
                } else {
                    // Local Mode Info & Action
                    Text(
                        text = "You are in local wired (USB) mode. Ensure cable is connected and server is running.",
                        fontSize = 12.sp,
                        color = Color(0xFF94A3B8)
                    )
                    Button(
                        onClick = {
                            ComposeBridgeAgent.resetToLocal(context)
                            onDismissRequest()
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF3B82F6)),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Reconnect Locally (127.0.0.1)", color = Color.White)
                    }
                }
            }
        }
    }
}
