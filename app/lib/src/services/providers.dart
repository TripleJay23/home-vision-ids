import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/config.dart';
import '../models/alert.dart';
import '../models/member.dart';
import 'api_client.dart';

/// Rebuilt whenever the configured backend URL changes, which in turn
/// refreshes anything that watches it.
final apiClientProvider = Provider<ApiClient>((ref) {
  final baseUrl = ref.watch(backendUrlProvider);
  return ApiClient(baseUrl);
});

/// Recent alerts. Invalidate (pull-to-refresh) to refetch.
final alertsProvider = FutureProvider<List<Alert>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.getAlerts();
});

/// Enrolled members.
final membersProvider = FutureProvider<List<Member>>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.getMembers();
});
