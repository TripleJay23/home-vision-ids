import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/selected_tab.dart';
import 'providers.dart';

// High-importance channel → sound + heads-up banner. The id MUST match the
// FCM default-channel meta-data in AndroidManifest.xml so background messages
// use it too.
const _channelId = 'high_importance_alerts';
const _channelName = 'Security Alerts';
const _channelDesc = 'Unknown-person detections from Home Vision IDS';

final FlutterLocalNotificationsPlugin _localNotifications =
    FlutterLocalNotificationsPlugin();

/// Background isolate handler — MUST be a top-level function with this pragma.
/// When the app is backgrounded/terminated the OS draws the notification from
/// the `notification` payload (routed to the high-importance channel via the
/// manifest), so there's nothing to do here.
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {}

final pushServiceProvider = Provider<PushService>((ref) => PushService(ref));

/// Connects firebase_messaging to the app: permission, token registration,
/// and showing real OS notifications (sound + heads-up) for alerts.
class PushService {
  final Ref ref;
  bool _started = false;

  PushService(this.ref);

  Future<void> start() async {
    if (_started) return;
    _started = true;
    try {
      await _initLocalNotifications();

      final messaging = FirebaseMessaging.instance;
      await messaging.requestPermission(); // Android 13+ prompts POST_NOTIFICATIONS

      final token = await messaging.getToken();
      if (token != null) await _register(token);
      messaging.onTokenRefresh.listen(_register);

      FirebaseMessaging.onMessage.listen(_onForeground);
      FirebaseMessaging.onMessageOpenedApp.listen(_onOpened);

      // App launched by tapping a notification while terminated.
      final initial = await messaging.getInitialMessage();
      if (initial != null) _onOpened(initial);
    } catch (_) {
      // Firebase/messaging unavailable (misconfig, or under tests) — non-fatal.
      _started = false;
    }
  }

  Future<void> _initLocalNotifications() async {
    const init = InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    );
    await _localNotifications.initialize(
      settings: init,
      onDidReceiveNotificationResponse: (_) => _goToAlerts(),
    );
    // Create the high-importance channel (idempotent) so foreground-shown and
    // background OS notifications both get sound + a heads-up banner.
    const channel = AndroidNotificationChannel(
      _channelId,
      _channelName,
      description: _channelDesc,
      importance: Importance.high,
    );
    await _localNotifications
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(channel);
  }

  Future<void> _register(String token) async {
    try {
      await ref.read(apiClientProvider).registerDevice(token);
    } catch (_) {
      // Backend unreachable right now; onTokenRefresh / next launch will retry.
    }
  }

  /// Foreground: Android won't draw a system notification itself, so we show a
  /// local one on the high-importance channel — giving the same sound + banner.
  void _onForeground(RemoteMessage message) {
    ref.invalidate(alertsProvider);
    final n = message.notification;
    _localNotifications.show(
      id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
      title: n?.title ?? 'Unknown person detected',
      body: n?.body ?? "Home Vision IDS spotted someone it doesn't recognise.",
      notificationDetails: const NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          channelDescription: _channelDesc,
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        ),
      ),
      payload: message.data['alert_id'] ?? '',
    );
  }

  void _onOpened(RemoteMessage message) => _goToAlerts();

  void _goToAlerts() {
    ref.read(selectedTabProvider.notifier).set(kAlertsTabIndex);
    ref.invalidate(alertsProvider);
  }
}
