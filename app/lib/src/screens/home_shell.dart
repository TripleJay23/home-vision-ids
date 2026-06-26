import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/push_service.dart';
import '../state/selected_tab.dart';
import 'alerts_screen.dart';
import 'live_view_screen.dart';
import 'members_screen.dart';
import 'settings_screen.dart';

/// Root scaffold with bottom navigation. IndexedStack keeps each tab's state
/// (and the live stream connection) alive while switching. The selected tab
/// lives in a provider so a push tap can jump to Alerts.
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  static const _screens = [
    LiveViewScreen(),
    AlertsScreen(),
    MembersScreen(),
    SettingsScreen(),
  ];

  @override
  void initState() {
    super.initState();
    // Start FCM (permission, token registration, listeners) after first frame.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(pushServiceProvider).start();
    });
  }

  @override
  Widget build(BuildContext context) {
    final index = ref.watch(selectedTabProvider);
    return Scaffold(
      body: IndexedStack(index: index, children: _screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (i) => ref.read(selectedTabProvider.notifier).set(i),
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.videocam_outlined), selectedIcon: Icon(Icons.videocam), label: 'Live'),
          NavigationDestination(
              icon: Icon(Icons.notifications_outlined), selectedIcon: Icon(Icons.notifications), label: 'Alerts'),
          NavigationDestination(
              icon: Icon(Icons.people_outline), selectedIcon: Icon(Icons.people), label: 'Members'),
          NavigationDestination(
              icon: Icon(Icons.settings_outlined), selectedIcon: Icon(Icons.settings), label: 'Settings'),
        ],
      ),
    );
  }
}
