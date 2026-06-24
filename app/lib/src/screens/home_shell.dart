import 'package:flutter/material.dart';

import 'alerts_screen.dart';
import 'live_view_screen.dart';
import 'members_screen.dart';
import 'settings_screen.dart';

/// Root scaffold with bottom navigation. IndexedStack keeps each tab's state
/// (and the live stream connection) alive while switching.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _index = 0;

  static const _screens = [
    LiveViewScreen(),
    AlertsScreen(),
    MembersScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
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
