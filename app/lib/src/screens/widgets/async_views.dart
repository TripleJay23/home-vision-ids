import 'package:flutter/material.dart';

import '../../services/api_client.dart';

/// Build the right error view for a failed fetch: an unreachable backend reads
/// as a connectivity problem, while a reachable backend that rejected the key
/// (401) or has no pipeline (503) is NOT a connectivity problem and must say so
/// — otherwise "couldn't reach the backend" is simply wrong and misleading.
Widget errorView(Object error, VoidCallback onRetry) {
  if (error is ApiException && !error.offline) {
    final msg = error.message.toLowerCase();
    final isAuth = msg.contains('unauthorized') || msg.contains('api key') || msg.contains('401');
    return ErrorRetry(
      message: error.message,
      onRetry: onRetry,
      title: isAuth ? 'API key rejected' : 'Backend error',
      icon: isAuth ? Icons.lock_outline : Icons.error_outline,
    );
  }
  return ErrorRetry(message: '$error', onRetry: onRetry);
}

/// Centered error message with a retry button. Used by the data screens.
class ErrorRetry extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  final String title;
  final IconData icon;

  const ErrorRetry({
    super.key,
    required this.message,
    required this.onRetry,
    this.title = "Couldn't reach the backend",
    this.icon = Icons.cloud_off_outlined,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 48, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 16),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(message, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 16),
            FilledButton.tonalIcon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Thin banner shown above cached data when the backend is unreachable.
class OfflineBanner extends StatelessWidget {
  const OfflineBanner({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      color: scheme.surfaceContainerHighest,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(
        children: [
          Icon(Icons.history, size: 16, color: scheme.onSurfaceVariant),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              'Showing last known · offline',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
            ),
          ),
        ],
      ),
    );
  }
}

/// Centered empty-state placeholder.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String detail;

  const EmptyState({super.key, required this.icon, required this.title, required this.detail});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
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
