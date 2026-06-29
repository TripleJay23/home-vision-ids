import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models/alert.dart';
import '../models/member.dart';

/// Sent on EVERY backend request (REST, MJPEG stream, and snapshot images).
/// Over an ngrok free tunnel, requests without this header get an HTML
/// "browser warning" interstitial instead of the real response, which breaks
/// JSON parsing and image loading. Harmless on a direct LAN backend (an unknown
/// header is ignored). See Phase 5 (remote access).
const Map<String, String> kBackendHeaders = {'ngrok-skip-browser-warning': 'true'};

/// Thin REST client for the Home Vision IDS FastAPI backend.
///
/// Stateless beyond [baseUrl] and [apiKey]; recreated by the provider whenever
/// the configured backend URL or API key changes.
class ApiClient {
  final String baseUrl;
  final String apiKey;
  ApiClient(this.baseUrl, [this.apiKey = '']);

  static const _timeout = Duration(seconds: 8);

  /// Headers for every request: the ngrok bypass plus the API key (when set).
  /// Use this everywhere — REST, the MJPEG stream, and snapshot fetches.
  Map<String, String> get headers => {
        ...kBackendHeaders,
        if (apiKey.isNotEmpty) 'X-API-Key': apiKey,
      };

  /// MJPEG live stream endpoint (consumed by MjpegView, not http here).
  String get streamUrl => '$baseUrl/stream';

  /// Turn an API-relative snapshot path into a fetchable absolute URL.
  String snapshotUrl(String apiPath) => '$baseUrl$apiPath';

  /// Download an alert snapshot's JPEG bytes (for saving to the gallery / cache).
  /// [url] is the already-resolved fetch URL (see [snapshotUrl]).
  Future<Uint8List> fetchSnapshotBytes(String url) async {
    final res = await http.get(Uri.parse(url), headers: headers).timeout(_timeout);
    if (res.statusCode != 200) {
      throw ApiException('Snapshot unavailable (HTTP ${res.statusCode}).');
    }
    return res.bodyBytes;
  }

  /// Quick reachability check against /health.
  Future<bool> ping() async {
    try {
      final res = await http.get(Uri.parse('$baseUrl/health'), headers: headers).timeout(_timeout);
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// GET helper that maps connection failures to a friendly offline message,
  /// so screens show "can't reach the backend" instead of a raw exception.
  Future<http.Response> _get(String path) async {
    try {
      return await http.get(Uri.parse('$baseUrl$path'), headers: headers).timeout(_timeout);
    } on TimeoutException {
      throw ApiException("Can't reach the backend — it timed out. Check it's running and the URL in Settings.", offline: true);
    } on SocketException {
      throw ApiException("Can't reach the backend. Check it's running and the URL in Settings.", offline: true);
    } on http.ClientException {
      throw ApiException("Can't reach the backend. Check it's running and the URL in Settings.", offline: true);
    }
  }

  Future<List<Alert>> getAlerts({int limit = 20}) async {
    final res = await _get('/alerts?limit=$limit');
    if (res.statusCode != 200) {
      throw ApiException(_describe('alerts', res.statusCode));
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final list = (body['alerts'] as List).cast<Map<String, dynamic>>();
    return list.map(Alert.fromJson).toList();
  }

  /// Register this device's FCM token as a push target (POST /devices).
  Future<void> registerDevice(String token) async {
    final res = await http
        .post(
          Uri.parse('$baseUrl/devices'),
          headers: {'Content-Type': 'application/json', ...headers},
          body: jsonEncode({'token': token}),
        )
        .timeout(_timeout);
    if (res.statusCode != 200) {
      throw ApiException('Device registration failed (HTTP ${res.statusCode}).');
    }
  }

  Future<List<Member>> getMembers() async {
    final res = await _get('/members');
    if (res.statusCode != 200) {
      throw ApiException(_describe('members', res.statusCode));
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final list = (body['members'] as List).cast<Map<String, dynamic>>();
    return list.map(Member.fromJson).toList();
  }

  // ── In-app enrollment ──────────────────────────────────────────────────

  /// Upload one captured enrollment photo for [name] under [pose].
  /// Returns the running count of photos saved for this member.
  Future<int> uploadPhoto(String name, String pose, List<int> bytes) async {
    final req = http.MultipartRequest('POST', Uri.parse('$baseUrl/members/$name/photos?pose=$pose'))
      ..headers.addAll(headers)
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: '$pose.jpg'));
    final res = await http.Response.fromStream(await req.send().timeout(const Duration(seconds: 20)));
    if (res.statusCode != 200) {
      throw ApiException('Photo upload failed (HTTP ${res.statusCode}).');
    }
    return (jsonDecode(res.body) as Map<String, dynamic>)['captured'] as int;
  }

  /// Build embeddings for [name] from the uploaded photos (heavy; ~tens of sec).
  /// Returns the resulting embedding count.
  Future<int> enrollMember(String name) async {
    final res = await http
        .post(Uri.parse('$baseUrl/members/$name/enroll'), headers: headers)
        .timeout(const Duration(seconds: 90));
    if (res.statusCode != 200) {
      throw ApiException(_detailOf(res) ?? 'Enrollment failed (HTTP ${res.statusCode}).');
    }
    return (jsonDecode(res.body) as Map<String, dynamic>)['embedding_count'] as int;
  }

  /// Remove a member (embeddings + photos).
  Future<void> deleteMember(String name) async {
    final res = await http
        .delete(Uri.parse('$baseUrl/members/$name'), headers: headers)
        .timeout(_timeout);
    if (res.statusCode != 200) {
      throw ApiException(_detailOf(res) ?? 'Delete failed (HTTP ${res.statusCode}).');
    }
  }

  String? _detailOf(http.Response res) {
    try {
      return (jsonDecode(res.body) as Map<String, dynamic>)['detail'] as String?;
    } catch (_) {
      return null;
    }
  }

  String _describe(String what, int code) {
    if (code == 401) {
      return 'Unauthorized — set the correct API key in Settings.';
    }
    if (code == 503) {
      return 'Vision pipeline not running (camera offline?). Start the backend and camera.';
    }
    return 'Failed to load $what (HTTP $code).';
  }
}

class ApiException implements Exception {
  final String message;

  /// True when the backend couldn't be reached at all (timeout/socket), as
  /// opposed to a reachable backend returning an error status (401/503). Lets
  /// callers fall back to cached data only when genuinely offline.
  final bool offline;

  ApiException(this.message, {this.offline = false});
  @override
  String toString() => message;
}
