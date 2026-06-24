import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'src/config/config.dart';
import 'src/screens/home_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
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
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.light, useMaterial3: true),
      darkTheme: ThemeData(colorSchemeSeed: seed, brightness: Brightness.dark, useMaterial3: true),
      themeMode: ThemeMode.system,
      home: const HomeShell(),
    );
  }
}
