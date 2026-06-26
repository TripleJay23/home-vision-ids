package com.homevision.home_vision_ids

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createAlertsChannel()
    }

    // Create the high-importance notification channel natively so it ALWAYS
    // exists once the app has been opened — background FCM messages (handled by
    // the system, not Dart) need this channel to pre-exist to make a sound and
    // show as a heads-up banner. Must match the id in AndroidManifest's
    // com.google.firebase.messaging.default_notification_channel_id meta-data.
    private fun createAlertsChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "high_importance_alerts",
                "Security Alerts",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Unknown-person detections from Home Vision IDS"
                enableVibration(true)
            }
            getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }
    }
}
