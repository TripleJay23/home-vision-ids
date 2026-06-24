import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:home_vision_ids/main.dart';
import 'package:home_vision_ids/src/config/config.dart';

void main() {
  testWidgets('App builds and shows the navigation tabs', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
        child: const HomeVisionApp(),
      ),
    );
    await tester.pump();

    expect(find.text('Live'), findsOneWidget);
    expect(find.text('Alerts'), findsOneWidget);
    expect(find.text('Members'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);
  });
}
