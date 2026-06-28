import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/config.dart';
import '../models/alert.dart';
import '../models/member.dart';
import 'api_client.dart';
import 'snapshot_cache.dart';

/// A fetch result that may have come from the local offline cache rather than a
/// live backend call. `fromCache == true` means the backend was unreachable and
/// this is the last successful response — screens use it to flag stale data.
class Offlineable<T> {
  final T data;
  final bool fromCache;
  const Offlineable(this.data, {this.fromCache = false});
}

/// Rebuilt whenever the configured backend URL changes, which in turn
/// refreshes anything that watches it.
final apiClientProvider = Provider<ApiClient>((ref) {
  final baseUrl = ref.watch(backendUrlProvider);
  return ApiClient(baseUrl);
});

/// On-device cache of alert snapshot bytes (durable evidence storage).
final snapshotCacheProvider = Provider<SnapshotCache>((ref) => SnapshotCache());

/// JPEG bytes for one alert's snapshot, cache-first: returns the on-device copy
/// if present; otherwise downloads it, caches it, and returns it; null if there
/// is no snapshot or the backend is unreachable and nothing is cached. Keyed by
/// a record so the family caches per (alertId, path) with value equality.
final snapshotBytesProvider =
    FutureProvider.family<Uint8List?, ({String alertId, String? path})>((ref, key) async {
  final cache = ref.read(snapshotCacheProvider);
  final cached = await cache.read(key.alertId);
  if (cached != null) return cached;
  if (key.path == null) return null;
  try {
    final api = ref.read(apiClientProvider);
    final bytes = await api.fetchSnapshotBytes(api.snapshotUrl(key.path!));
    await cache.write(key.alertId, bytes);
    return bytes;
  } catch (_) {
    return null;
  }
});

const _kCacheAlerts = 'cache_alerts';
const _kCacheMembers = 'cache_members';

/// Generic "fetch live, fall back to cache" helper. On success the response is
/// persisted as JSON; on failure the last cached response is returned (flagged
/// `fromCache`), or the error is rethrown if there is no cache yet (so the
/// screen shows its "can't reach the backend" state on a cold offline start).
Future<Offlineable<List<T>>> _fetchCached<T>({
  required Ref ref,
  required String cacheKey,
  required Future<List<T>> Function() fetch,
  required Map<String, dynamic> Function(T) toJson,
  required T Function(Map<String, dynamic>) fromJson,
}) async {
  final prefs = ref.read(sharedPreferencesProvider);
  try {
    final items = await fetch();
    await prefs.setString(cacheKey, jsonEncode(items.map(toJson).toList()));
    return Offlineable(items);
  } catch (e) {
    final cached = prefs.getString(cacheKey);
    if (cached != null) {
      final list = (jsonDecode(cached) as List).cast<Map<String, dynamic>>().map(fromJson).toList();
      return Offlineable(list, fromCache: true);
    }
    rethrow;
  }
}

/// Recent alerts, with offline fallback to the last successful fetch.
final alertsProvider = FutureProvider<Offlineable<List<Alert>>>((ref) {
  final api = ref.watch(apiClientProvider);
  return _fetchCached<Alert>(
    ref: ref,
    cacheKey: _kCacheAlerts,
    fetch: api.getAlerts,
    toJson: (a) => a.toJson(),
    fromJson: Alert.fromJson,
  );
});

/// Enrolled members, with offline fallback to the last successful fetch.
final membersProvider = FutureProvider<Offlineable<List<Member>>>((ref) {
  final api = ref.watch(apiClientProvider);
  return _fetchCached<Member>(
    ref: ref,
    cacheKey: _kCacheMembers,
    fetch: api.getMembers,
    toJson: (m) => m.toJson(),
    fromJson: Member.fromJson,
  );
});
