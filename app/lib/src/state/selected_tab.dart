import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Index of the Alerts tab within HomeShell.
const int kAlertsTabIndex = 1;

/// Currently selected bottom-nav tab. Held in a provider (not local widget
/// state) so a push-notification tap can switch tabs programmatically.
class SelectedTab extends Notifier<int> {
  @override
  int build() => 0;

  void set(int index) => state = index;
}

final selectedTabProvider = NotifierProvider<SelectedTab, int>(SelectedTab.new);
