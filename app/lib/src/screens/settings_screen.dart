import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/config.dart';
import '../services/providers.dart';

/// Configure the backend base URL (and test reachability). This is what lets
/// the same build work on home WiFi (LAN IP) or remotely (ngrok/relay URL)
/// without rebuilding.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _controller;
  bool _testing = false;

  late final TextEditingController _keyController;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: ref.read(backendUrlProvider));
    _keyController = TextEditingController(text: ref.read(apiKeyProvider));
  }

  @override
  void dispose() {
    _controller.dispose();
    _keyController.dispose();
    super.dispose();
  }

  /// Persist URL + key without any UI feedback. Shared by Save and Test so both
  /// act on exactly what's in the fields right now.
  Future<void> _persist() async {
    final url = _controller.text.trim();
    if (url.isNotEmpty) {
      await ref.read(backendUrlProvider.notifier).setUrl(url);
    }
    await ref.read(apiKeyProvider.notifier).setKey(_keyController.text);
    if (!mounted) return;
    _controller.text = ref.read(backendUrlProvider);
    _keyController.text = ref.read(apiKeyProvider);
  }

  void _snack(String message, {Color? background}) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        content: Text(message),
        backgroundColor: background,
        duration: const Duration(seconds: 4),
      ));
  }

  Future<void> _save() async {
    if (_controller.text.trim().isEmpty) {
      _snack('Enter a backend URL first.', background: Theme.of(context).colorScheme.error);
      return;
    }
    await _persist();
    if (!mounted) return;
    _snack('Settings saved.');
  }

  /// Actually exercise the configured URL + key against an authenticated
  /// endpoint and report the real result — reachable + key accepted, wrong key,
  /// or unreachable — instead of a blanket "connected".
  Future<void> _testConnection() async {
    if (_controller.text.trim().isEmpty) {
      _snack('Enter a backend URL first.', background: Theme.of(context).colorScheme.error);
      return;
    }
    await _persist(); // test exactly what's configured
    if (!mounted) return;
    setState(() => _testing = true);
    final result = await ref.read(apiClientProvider).verify();
    if (!mounted) return;
    setState(() => _testing = false);
    _snack(
      result.message,
      background: result.ok ? Colors.green.shade700 : Theme.of(context).colorScheme.error,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Backend connection', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          TextField(
            controller: _controller,
            keyboardType: TextInputType.url,
            autocorrect: false,
            decoration: const InputDecoration(
              labelText: 'Backend base URL',
              hintText: kDefaultBackendUrl,
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.dns_outlined),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _keyController,
            autocorrect: false,
            obscureText: true,
            decoration: const InputDecoration(
              labelText: 'API key',
              hintText: "Matches the backend's API_SECRET_KEY",
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.key_outlined),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: FilledButton.icon(
                  onPressed: _save,
                  icon: const Icon(Icons.save_outlined),
                  label: const Text('Save'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.tonalIcon(
                  onPressed: _testing ? null : _testConnection,
                  icon: _testing
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.wifi_tethering),
                  label: const Text('Test'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: const [
                    Icon(Icons.info_outline, size: 20),
                    SizedBox(width: 8),
                    Text('Connecting your phone'),
                  ]),
                  const SizedBox(height: 8),
                  Text(
                    '• Same WiFi: use the laptop\'s LAN IP, e.g. $kDefaultBackendUrl\n'
                    '• Phone and laptop must be on the same network.\n'
                    '• Remote access: use an ngrok/relay URL instead.\n'
                    '• A phone can never reach the backend\'s "localhost".',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
