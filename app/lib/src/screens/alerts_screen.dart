import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/alert.dart';
import '../services/api_client.dart';
import '../services/providers.dart';
import '../utils/format.dart';
import 'widgets/async_views.dart';

/// Recent unknown-person alerts from /alerts.
class AlertsScreen extends ConsumerWidget {
  const AlertsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alertsAsync = ref.watch(alertsProvider);
    final api = ref.watch(apiClientProvider);

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
        data: (alerts) {
          if (alerts.isEmpty) {
            return const EmptyState(
              icon: Icons.notifications_off_outlined,
              title: 'No alerts yet',
              detail: 'Unknown-person alerts will show up here.',
            );
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(alertsProvider),
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: alerts.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, i) => _AlertCard(alert: alerts[i], api: api),
            ),
          );
        },
      ),
    );
  }
}

class _AlertCard extends StatelessWidget {
  final Alert alert;
  final ApiClient api;

  const _AlertCard({required this.alert, required this.api});

  @override
  Widget build(BuildContext context) {
    final url = alert.snapshotUrl != null ? api.snapshotUrl(alert.snapshotUrl!) : null;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: url == null ? null : () => _showFull(context, url),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: SizedBox(
                  width: 72,
                  height: 72,
                  child: url == null
                      ? const ColoredBox(color: Colors.black12, child: Icon(Icons.image_not_supported_outlined))
                      : Image.network(url, fit: BoxFit.cover, headers: kBackendHeaders,
                          errorBuilder: (_, _, _) =>
                              const ColoredBox(color: Colors.black12, child: Icon(Icons.broken_image_outlined))),
                ),
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
              if (url != null) const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }

  String _reasonLabel(String reason) =>
      reason == 'unknown_person' ? 'Unknown person detected' : reason;

  void _showFull(BuildContext context, String url) {
    showDialog<void>(
      context: context,
      builder: (_) => Dialog(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            InteractiveViewer(child: Image.network(url, headers: kBackendHeaders)),
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Close')),
          ],
        ),
      ),
    );
  }
}
