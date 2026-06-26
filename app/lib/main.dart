import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'src/config/config.dart';
import 'src/screens/home_shell.dart';
import 'src/services/app_messenger.dart';
import 'src/services/push_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Firebase + FCM. If Firebase isn't configured on this build, don't block the
  // app from starting — the stream/alerts/members features work without push.
  try {
    await Firebase.initializeApp();
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
  } catch (_) {
    // No google-services config / Firebase unavailable — push just stays off.
  }

  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      // The whole app reads config from SharedPreferences; load it once here
      // and inject it so providers can access it synchronously.
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: const HomeVisionApp(),
    ),
  );
}

class HomeVisionApp extends StatelessWidget {
  const HomeVisionApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF1565C0);
    return MaterialApp(
      title: 'Home Vision IDS',
      scaffoldMessengerKey: appMessengerKey,
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.light, useMaterial3: true),
      darkTheme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.dark, useMaterial3: true),
      themeMode: ThemeMode.system,
      home: const HomeShell(),
    );
  }
}
