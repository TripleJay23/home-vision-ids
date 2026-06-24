import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

/// Renders an MJPEG (`multipart/x-mixed-replace`) HTTP stream.
///
/// Flutter's `Image.network` only loads a single image, so it can't drive a
/// continuous MJPEG feed. This widget opens a streaming GET, scans the incoming
/// bytes for complete JPEG frames (SOI 0xFFD8 … EOI 0xFFD9) and swaps each one
/// into an `Image.memory` with gapless playback.
///
/// To force a reconnect, give the widget a new [key].
class MjpegView extends StatefulWidget {
  final String streamUrl;
  final BoxFit fit;

  const MjpegView({super.key, required this.streamUrl, this.fit = BoxFit.contain});

  @override
  State<MjpegView> createState() => _MjpegViewState();
}

class _MjpegViewState extends State<MjpegView> {
  static const int _markerStart = 0xD8; // second byte of SOI (FF D8)
  static const int _markerEnd = 0xD9; // second byte of EOI (FF D9)
  static const int _maxBuffer = 2 << 20; // 2 MB guard against runaway growth

  http.Client? _client;
  StreamSubscription<List<int>>? _sub;
  final List<int> _buffer = <int>[];
  Uint8List? _frame;
  String? _error;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  Future<void> _connect() async {
    setState(() => _error = null);
    try {
      final client = http.Client();
      _client = client;
      final request = http.Request('GET', Uri.parse(widget.streamUrl));
      final response = await client.send(request);
      if (response.statusCode != 200) {
        throw response.statusCode == 503
            ? 'Pipeline not running (camera offline?)'
            : 'Stream error (HTTP ${response.statusCode})';
      }
      if (!mounted) {
        client.close();
        return;
      }
      _sub = response.stream.listen(
        _onData,
        onError: (Object e) => _fail('$e'),
        onDone: () => _fail('Stream closed'),
        cancelOnError: true,
      );
    } catch (e) {
      _fail('$e');
    }
  }

  void _onData(List<int> chunk) {
    _buffer.addAll(chunk);
    while (true) {
      final start = _findMarker(_markerStart, 0);
      if (start < 0) {
        if (_buffer.length > _maxBuffer) _buffer.clear();
        break;
      }
      final end = _findMarker(_markerEnd, start + 2);
      if (end < 0) {
        if (start > 0) _buffer.removeRange(0, start); // drop pre-frame noise
        break;
      }
      final frameEnd = end + 2;
      final frame = Uint8List.fromList(_buffer.sublist(start, frameEnd));
      _buffer.removeRange(0, frameEnd);
      if (mounted) setState(() => _frame = frame);
    }
  }

  /// Index of `0xFF <marker>` at or after [from], else -1.
  int _findMarker(int marker, int from) {
    for (int i = from; i < _buffer.length - 1; i++) {
      if (_buffer[i] == 0xFF && _buffer[i + 1] == marker) return i;
    }
    return -1;
  }

  void _fail(String message) {
    if (!mounted) return;
    setState(() => _error = message);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _client?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null && _frame == null) {
      return _StreamMessage(
        icon: Icons.videocam_off_outlined,
        title: 'No live feed',
        detail: _error!,
      );
    }
    if (_frame == null) {
      return const _StreamMessage(
        icon: Icons.hourglass_empty,
        title: 'Connecting…',
        detail: 'Waiting for the first frame.',
        showSpinner: true,
      );
    }
    return Image.memory(_frame!, fit: widget.fit, gaplessPlayback: true);
  }
}

class _StreamMessage extends StatelessWidget {
  final IconData icon;
  final String title;
  final String detail;
  final bool showSpinner;

  const _StreamMessage({
    required this.icon,
    required this.title,
    required this.detail,
    this.showSpinner = false,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (showSpinner)
              const CircularProgressIndicator()
            else
              Icon(icon, size: 48, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 16),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(detail, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}
