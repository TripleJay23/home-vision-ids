import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/providers.dart';
import 'widgets/async_views.dart';

/// Enrolled household members from /members.
class MembersScreen extends ConsumerWidget {
  const MembersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final membersAsync = ref.watch(membersProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Members'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: () => ref.invalidate(membersProvider),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: membersAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(message: '$e', onRetry: () => ref.invalidate(membersProvider)),
        data: (members) {
          if (members.isEmpty) {
            return const EmptyState(
              icon: Icons.person_off_outlined,
              title: 'No one enrolled',
              detail: 'Enroll people with the capture_enrollment_frames.py script.',
            );
          }
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(membersProvider),
            child: ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: members.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final m = members[i];
                return ListTile(
                  leading: CircleAvatar(child: Text(m.name.isNotEmpty ? m.name[0].toUpperCase() : '?')),
                  title: Text(m.name),
                  subtitle: m.enrolledAt != null ? Text('enrolled ${m.enrolledAt}') : null,
                  trailing: Text('${m.embeddingCount} samples'),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
