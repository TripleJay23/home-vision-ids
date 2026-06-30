import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/member.dart';
import '../services/providers.dart';
import '../utils/format.dart';
import 'enroll_member_screen.dart';
import 'widgets/async_views.dart';

/// Enrolled household members from /members, with in-app enroll + delete.
///
/// Enrollment builds run in the background on the server, so a freshly added
/// member first appears as "Enrolling…" and flips to "Enrolled" once its
/// embeddings are built. While any member is enrolling, this screen polls
/// /members so that transition shows up without a manual refresh.
class MembersScreen extends ConsumerStatefulWidget {
  const MembersScreen({super.key});

  @override
  ConsumerState<MembersScreen> createState() => _MembersScreenState();
}

class _MembersScreenState extends ConsumerState<MembersScreen> {
  Timer? _poll;

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  /// Run a 3s poll only while at least one member is mid-build.
  void _syncPolling({required bool anyEnrolling}) {
    if (anyEnrolling) {
      _poll ??= Timer.periodic(
        const Duration(seconds: 3),
        (_) => ref.invalidate(membersProvider),
      );
    } else {
      _poll?.cancel();
      _poll = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final membersAsync = ref.watch(membersProvider);
    final anyEnrolling = membersAsync.asData?.value.data.any((m) => m.isEnrolling) ?? false;
    // Start/stop the poll after this frame (can't touch a Timer mid-build).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _syncPolling(anyEnrolling: anyEnrolling);
    });

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
        error: (e, _) => errorView(e, () => ref.invalidate(membersProvider)),
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
                    subtitle: _subtitle(context, m),
                    trailing: _trailing(context, m),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }

  Widget? _subtitle(BuildContext context, Member m) {
    if (m.isEnrolling) return const Text('building face profile…');
    if (m.isFailed) {
      return Text(m.error ?? 'enrollment failed',
          style: TextStyle(color: Theme.of(context).colorScheme.error));
    }
    return m.enrolledAt != null ? Text('enrolled ${timeAgo(m.enrolledAt!)}') : null;
  }

  Widget _trailing(BuildContext context, Member m) {
    if (m.isEnrolling) {
      return const Chip(
        avatar: SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
        label: Text('Enrolling…'),
        visualDensity: VisualDensity.compact,
      );
    }
    if (m.isFailed) {
      return Chip(
        avatar: Icon(Icons.error_outline, size: 18, color: Theme.of(context).colorScheme.error),
        label: const Text('Failed'),
        visualDensity: VisualDensity.compact,
      );
    }
    return Chip(
      avatar: const Icon(Icons.face_outlined, size: 18),
      label: Text('${m.embeddingCount}'),
      visualDensity: VisualDensity.compact,
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
