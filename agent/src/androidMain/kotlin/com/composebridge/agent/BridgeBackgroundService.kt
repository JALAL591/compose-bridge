package com.composebridge.agent

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat

/**
 * BridgeBackgroundService — Keeps WebSocket alive and displays ongoing notifications & build progress.
 */
class BridgeBackgroundService : Service() {

    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannels()
        acquireLocks()
        Log.d(TAG, "🟢 BridgeBackgroundService created & locks acquired")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val message = intent?.getStringExtra(EXTRA_STATUS_MSG) ?: "ComposeBridge is active & connected"
        val notification = buildOngoingNotification(message)
        startForeground(NOTIFICATION_ID, notification)
        return START_STICKY
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        // Keep service & socket alive even if app is swiped away from recents
        Log.d(TAG, "📱 App task removed from recents — keeping BridgeBackgroundService alive")
        super.onTaskRemoved(rootIntent)
    }

    override fun onDestroy() {
        releaseLocks()
        Log.d(TAG, "🛑 BridgeBackgroundService destroyed & locks released")
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    @Suppress("DEPRECATION")
    private fun acquireLocks() {
        try {
            val pm = getSystemService(Context.POWER_SERVICE) as? PowerManager
            wakeLock = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "composebridge:wakelock")?.apply {
                setReferenceCounted(false)
                acquire(24 * 60 * 60 * 1000L) // 24 hours max
            }

            val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            wifiLock = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                wm?.createWifiLock(WifiManager.WIFI_MODE_FULL_LOW_LATENCY, "composebridge:wifilock")
            } else {
                wm?.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "composebridge:wifilock")
            }?.apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to acquire WakeLock / WifiLock: ${e.message}")
        }
    }

    private fun releaseLocks() {
        try {
            wakeLock?.let {
                if (it.isHeld) it.release()
            }
            wakeLock = null

            wifiLock?.let {
                if (it.isHeld) it.release()
            }
            wifiLock = null
        } catch (_: Exception) {}
    }

    private fun createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return

            val ongoingChannel = NotificationChannel(
                CHANNEL_ID_ONGOING,
                "ComposeBridge Service",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows active ComposeBridge connection status"
                setShowBadge(false)
            }
            nm.createNotificationChannel(ongoingChannel)

            val buildChannel = NotificationChannel(
                CHANNEL_ID_BUILD,
                "ComposeBridge APK Builds",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Shows APK build and download progress"
            }
            nm.createNotificationChannel(buildChannel)
        }
    }

    private fun buildOngoingNotification(statusText: String) =
        NotificationCompat.Builder(this, CHANNEL_ID_ONGOING)
            .setContentTitle("ComposeBridge Developer Agent")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setOngoing(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .build()

    companion object {
        private const val TAG = "BridgeBgService"
        private const val NOTIFICATION_ID = 8711
        private const val BUILD_NOTIFICATION_ID = 8712
        private const val CHANNEL_ID_ONGOING = "composebridge_service_channel"
        private const val CHANNEL_ID_BUILD = "composebridge_build_channel"
        private const val EXTRA_STATUS_MSG = "extra_status_msg"

        fun start(context: Context, statusMessage: String = "ComposeBridge is active & connected") {
            try {
                val intent = Intent(context, BridgeBackgroundService::class.java).apply {
                    putExtra(EXTRA_STATUS_MSG, statusMessage)
                }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                Log.w(TAG, "Failed to start BridgeBackgroundService: ${e.message}")
            }
        }

        fun stop(context: Context) {
            try {
                context.stopService(Intent(context, BridgeBackgroundService::class.java))
            } catch (_: Exception) {}
        }

        fun updateBuildProgress(context: Context, progressPercent: Int, message: String) {
            try {
                val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
                val builder = NotificationCompat.Builder(context, CHANNEL_ID_BUILD)
                    .setContentTitle("ComposeBridge: Building APK...")
                    .setContentText(if (message.isNotBlank()) message else "$progressPercent%")
                    .setSmallIcon(android.R.drawable.stat_sys_download)
                    .setOngoing(true)
                    .setProgress(100, progressPercent.coerceIn(0, 100), progressPercent <= 0)
                    .setPriority(NotificationCompat.PRIORITY_HIGH)
                    .setOnlyAlertOnce(true)
                    .setSilent(true)

                nm.notify(BUILD_NOTIFICATION_ID, builder.build())
            } catch (e: Exception) {
                Log.w(TAG, "Failed to update build progress notification: ${e.message}")
            }
        }

        fun showApkDownloadedNotification(context: Context, apkUri: Uri, fileName: String) {
            try {
                val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager ?: return
                // Dismiss ongoing progress notification
                nm.cancel(BUILD_NOTIFICATION_ID)

                val installIntent = Intent(Intent.ACTION_VIEW).apply {
                    setDataAndType(apkUri, "application/vnd.android.package-archive")
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                val pendingIntent = PendingIntent.getActivity(
                    context,
                    0,
                    installIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) PendingIntent.FLAG_IMMUTABLE else 0)
                )

                val builder = NotificationCompat.Builder(context, CHANNEL_ID_BUILD)
                    .setContentTitle("APK Downloaded 🎉")
                    .setContentText("Tap to install: $fileName")
                    .setSmallIcon(android.R.drawable.stat_sys_download_done)
                    .setAutoCancel(true)
                    .setContentIntent(pendingIntent)
                    .setPriority(NotificationCompat.PRIORITY_HIGH)

                nm.notify(BUILD_NOTIFICATION_ID + 1, builder.build())
            } catch (e: Exception) {
                Log.w(TAG, "Failed to post APK downloaded notification: ${e.message}")
            }
        }
    }
}
