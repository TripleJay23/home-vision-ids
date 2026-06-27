package com.homevision.home_vision_ids

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setUpAlertsChannel()
    }

    // Create the high-importance notification channel natively so it always
    // exists before any background FCM message arrives (background notifications
    // need the channel to pre-exist to show + vibrate). It uses the SYSTEM
    // default notification sound — the user keeps their own choice. Must match
    // the FCM default-channel meta-data in AndroidManifest.
    //
    // Also deletes the old bundled-custom-sound channel ("hv_security_alerts")
    // so it stops appearing as a duplicate entry in the app's notification
    // settings.
    private fun setUpAlertsChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.deleteNotificationChannel("hv_security_alerts")
            val channel = NotificationChannel(
                "high_importance_alerts",
                "Security Alerts",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Unknown-person detections from Home Vision IDS"
                enableVibration(true)
            }
            manager.createNotificationChannel(channel)
        }
    }
}
