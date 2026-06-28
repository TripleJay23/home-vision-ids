import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gal/gal.dart';

import '../models/alert.dart';
import '../services/providers.dart';
import '../utils/format.dart';
import 'widgets/async_views.dart';

/// Recent unknown-person alerts from /alerts, with offline fallback to the
/// last-known list (cached) and a "Save to gallery" evidence action.
class AlertsScreen extends ConsumerWidget {
  const AlertsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alertsAsync = ref.watch(alertsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: () => ref.invalidate(alertsProvider),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: alertsAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(message: '$e', onRetry: () => ref.invalidate(alertsProvider)),
        data: (res) {
          final alerts = res.data;
          if (alerts.isEmpty) {
            return const EmptyState(
              icon: Icons.notifications_off_outlined,
              title: 'No alerts yet',
              detail: 'Unknown-person alerts will show up here.',
            );
          }
          final list = RefreshIndicator(
            onRefresh: () async => ref.invalidate(alertsProvider),
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: alerts.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, i) => _AlertCard(alert: alerts[i]),
            ),
          );
          // Offline: flag stale data and dim the list, but still show it.
          if (res.fromCache) {
            return Column(
              children: [
                const OfflineBanner(),
                Expanded(child: Opacity(opacity: 0.6, child: list)),
              ],
            );
          }
          return list;
        },
      ),
    );
  }
}

class _AlertCard extends ConsumerWidget {
  final Alert alert;

  const _AlertCard({required this.alert});

  ({String alertId, String? path}) get _key => (alertId: alert.alertId, path: alert.snapshotUrl);

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bytesAsync = ref.watch(snapshotBytesProvider(_key));
    final bytes = bytesAsync.asData?.value;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: bytes == null ? null : () => _showFull(context, ref, bytes),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: SizedBox(width: 72, height: 72, child: _thumb(bytes)),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.person_off_outlined, size: 18, color: Theme.of(context).colorScheme.error),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(_reasonLabel(alert.reason),
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(Icons.schedule, size: 14, color: Theme.of(context).textTheme.bodySmall?.color),
                        const SizedBox(width: 4),
                        Text(timeAgo(alert.createdAt), style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                    if (alert.distance != null)
                      Text('distance ${alert.distance!.toStringAsFixed(3)} · track #${alert.trackId}',
                          style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Save to gallery',
                onPressed: alert.snapshotUrl == null ? null : () => _saveToGallery(context, ref),
                icon: const Icon(Icons.download_outlined),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _thumb(Uint8List? bytes) {
    if (bytes != null) return Image.memory(bytes, fit: BoxFit.cover);
    return ColoredBox(
      color: Colors.black12,
      child: Icon(alert.snapshotUrl == null ? Icons.image_not_supported_outlined : Icons.broken_image_outlined),
    );
  }

  String _reasonLabel(String reason) =>
      reason == 'unknown_person' ? 'Unknown person detected' : reason;

  void _showFull(BuildContext context, WidgetRef ref, Uint8List bytes) {
    showDialog<void>(
      context: context,
      builder: (_) => Dialog(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            InteractiveViewer(child: Image.memory(bytes)),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                TextButton.icon(
                  onPressed: () => _saveToGallery(context, ref),
                  icon: const Icon(Icons.download_outlined),
                  label: const Text('Save to gallery'),
                ),
                TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// Save this alert's snapshot to the phone gallery for evidence. Uses the
  /// on-device cache when available (works offline / after a backend restart),
  /// otherwise downloads and caches it.
  Future<void> _saveToGallery(BuildContext context, WidgetRef ref) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final bytes = await ref.read(snapshotBytesProvider(_key).future);
      if (bytes == null) {
        messenger.showSnackBar(const SnackBar(content: Text('No snapshot to save — backend unreachable.')));
        return;
      }
      if (!await Gal.hasAccess()) await Gal.requestAccess();
      await Gal.putImageBytes(bytes, name: 'home_vision_${alert.alertId}');
      messenger.showSnackBar(const SnackBar(content: Text('Saved to gallery')));
    } on GalException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Could not save: ${e.type.message}')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Could not save: $e')));
    }
  }
}
