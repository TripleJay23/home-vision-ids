import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Injected in main() once SharedPreferences has loaded. Reading it before the
/// override is wired is a programming error, hence the throw.
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('sharedPreferencesProvider must be overridden in main()');
});

/// Default points at this dev machine's LAN IP so a phone on the same WiFi
/// works on first launch. Override it in Settings for another network or an
/// ngrok/relay URL — a phone can never reach the backend's "localhost".
const String kDefaultBackendUrl = 'http://192.168.1.153:8000';

const String _kBackendUrlKey = 'backend_url';

/// Holds the backend base URL, persisted to SharedPreferences.
class BackendUrlNotifier extends Notifier<String> {
  @override
  String build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getString(_kBackendUrlKey) ?? kDefaultBackendUrl;
  }

  /// Persist a new backend URL (trailing slashes trimmed) and update state.
  Future<void> setUrl(String url) async {
    final cleaned = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(_kBackendUrlKey, cleaned);
    state = cleaned;
  }
}

final backendUrlProvider =
    NotifierProvider<BackendUrlNotifier, String>(BackendUrlNotifier.new);
