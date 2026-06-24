import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/config.dart';
import '../widgets/mjpeg_view.dart';

/// Live annotated MJPEG feed from the backend's /stream endpoint.
class LiveViewScreen extends ConsumerStatefulWidget {
  const LiveViewScreen({super.key});

  @override
  ConsumerState<LiveViewScreen> createState() => _LiveViewScreenState();
}

class _LiveViewScreenState extends ConsumerState<LiveViewScreen> {
  // Bumping this rebuilds MjpegView with a fresh key, forcing a reconnect.
  int _reconnectToken = 0;

  @override
  Widget build(BuildContext context) {
    final baseUrl = ref.watch(backendUrlProvider);
    final streamUrl = '$baseUrl/stream';
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live View'),
        actions: [
          IconButton(
            tooltip: 'Reconnect',
            onPressed: () => setState(() => _reconnectToken++),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Container(
        color: Colors.black,
        alignment: Alignment.center,
        child: MjpegView(
          key: ValueKey('$streamUrl#$_reconnectToken'),
          streamUrl: streamUrl,
        ),
      ),
    );
  }
}
