import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/providers.dart';
import '../utils/format.dart';
import 'enroll_member_screen.dart';
import 'widgets/async_views.dart';

/// Enrolled household members from /members, with in-app enroll + delete.
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
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const EnrollMemberScreen()),
          );
          ref.invalidate(membersProvider); // refresh roster on return
        },
        icon: const Icon(Icons.person_add_alt_1),
        label: const Text('Enroll'),
      ),
      body: membersAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorRetry(message: '$e', onRetry: () => ref.invalidate(membersProvider)),
        data: (res) {
          final members = res.data;
          if (members.isEmpty) {
            return const EmptyState(
              icon: Icons.person_off_outlined,
              title: 'No one enrolled',
              detail: 'Tap Enroll to add a household member from the camera.',
            );
          }
          // Members are the registered roster — durable registry data, not
          // cached stream shots — so they always render the same whether served
          // live or from the offline cache. No staleness banner.
          return RefreshIndicator(
            onRefresh: () async => ref.invalidate(membersProvider),
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 88), // room for the FAB
              itemCount: members.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final m = members[i];
                final display = m.name.isEmpty
                    ? '?'
                    : '${m.name[0].toUpperCase()}${m.name.substring(1)}';
                return Dismissible(
                  key: ValueKey(m.name),
                  direction: DismissDirection.endToStart,
                  confirmDismiss: (_) => _confirmAndDelete(context, ref, m.name),
                  background: Container(
                    color: Theme.of(context).colorScheme.errorContainer,
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 20),
                    child: Icon(Icons.delete_outline, color: Theme.of(context).colorScheme.onErrorContainer),
                  ),
                  child: ListTile(
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
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  /// Confirm + delete a member. Returns true if it was deleted (so Dismissible
  /// removes the row).
  Future<bool> _confirmAndDelete(BuildContext context, WidgetRef ref, String name) async {
    final ok = await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: Text('Remove "$name"?'),
            content: const Text('This deletes their face profile and photos. They will no longer be recognised.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Remove')),
            ],
          ),
        ) ??
        false;
    if (!ok) return false;
    try {
      await ref.read(apiClientProvider).deleteMember(name);
      // Evict from the offline cache too, so a deleted member can't reappear in
      // the roster if the backend drops before the next fetch.
      await removeMemberFromCache(ref, name);
      ref.invalidate(membersProvider);
      return true;
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Delete failed: $e')));
      }
      return false;
    }
  }
}
