package com.homevision.home_vision_ids

import android.app.NotificationChannel
import android.app.NotificationManager
import android.media.AudioAttributes
import android.net.Uri
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createAlertsChannel()
    }

    // Create the high-importance notification channel natively, with the app's
    // OWN bundled sound (res/raw/alert.wav) and an explicit vibration pattern,
    // so alerts are always audible and buzz REGARDLESS of the phone's default
    // notification sound (which may be set to "None"). Channels are immutable
    // once created, so adding a bundled sound required a fresh channel id
    // ("hv_security_alerts"); it must match the FCM default-channel meta-data in
    // AndroidManifest. Created on every launch (idempotent) so it exists before
    // any background FCM message arrives.
    private fun createAlertsChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val soundUri = Uri.parse("android.resource://$packageName/raw/alert")
            val audioAttributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build()
            val channel = NotificationChannel(
                "hv_security_alerts",
                "Security Alerts",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "Unknown-person detections from Home Vision IDS"
                setSound(soundUri, audioAttributes)
                enableVibration(true)
                vibrationPattern = longArrayOf(0, 350, 200, 350)
                enableLights(true)
            }
            getSystemService(NotificationManager::class.java)
                .createNotificationChannel(channel)
        }
    }
}
