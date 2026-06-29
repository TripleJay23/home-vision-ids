import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/config.dart';
import '../services/providers.dart';
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
    final headers = ref.watch(apiClientProvider).headers;
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
      body: Column(
        children: [
          Expanded(
            child: Stack(
              children: [
                Container(
                  width: double.infinity,
                  color: Colors.black,
                  alignment: Alignment.center,
                  child: MjpegView(
                    // Include the key so changing it in Settings forces a reconnect.
                    key: ValueKey('$streamUrl#$_reconnectToken#${headers['X-API-Key'] ?? ''}'),
                    streamUrl: streamUrl,
                    headers: headers,
                  ),
                ),
                const Positioned(top: 12, left: 12, child: _LiveBadge()),
              ],
            ),
          ),
          const _RecognitionLegend(),
        ],
      ),
    );
  }
}

/// "● LIVE" pill overlaid on the stream.
class _LiveBadge extends StatelessWidget {
  const _LiveBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(20)),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.fiber_manual_record, color: Colors.redAccent, size: 12),
          SizedBox(width: 6),
          Text('LIVE', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 1)),
        ],
      ),
    );
  }
}

/// Legend explaining the box colours the backend draws on the stream.
class _RecognitionLegend extends StatelessWidget {
  const _RecognitionLegend();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 10),
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: 18,
        runSpacing: 6,
        children: [
          _LegendDot(color: Color(0xFF80FF00), label: 'Known'),
          _LegendDot(color: Color(0xFFFF5000), label: 'Stranger'),
          _LegendDot(color: Color(0xFF00C8C8), label: 'Identifying'),
        ],
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
