import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/providers.dart';
import '../utils/format.dart';
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
                final display = m.name.isEmpty
                    ? '?'
                    : '${m.name[0].toUpperCase()}${m.name.substring(1)}';
                return ListTile(
                  leading: CircleAvatar(
                    backgroundColor: colorForName(m.name),
                    foregroundColor: Colors.white,
                    child: Text(m.name.isNotEmpty ? m.name[0].toUpperCase() : '?'),
                  ),
                  title: Text(display, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: m.enrolledAt != null ? Text('enrolled ${timeAgo(m.enrolledAt!)}') : null,
                  trailing: Chip(
                    avatar: const Icon(Icons.face_outlined, size: 18),
                    label: Text('${m.embeddingCount}'),
                    visualDensity: VisualDensity.compact,
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
