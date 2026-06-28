import 'dart:async';
import 'dart:convert';
import 'dart:io';

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
/// Stateless beyond [baseUrl]; recreated by the provider whenever the
/// configured backend URL changes.
class ApiClient {
  final String baseUrl;
  ApiClient(this.baseUrl);

  static const _timeout = Duration(seconds: 8);

  /// MJPEG live stream endpoint (consumed by MjpegView, not http here).
  String get streamUrl => '$baseUrl/stream';

  /// Turn an API-relative snapshot path into a fetchable absolute URL.
  String snapshotUrl(String apiPath) => '$baseUrl$apiPath';

  /// Quick reachability check against /health.
  Future<bool> ping() async {
    try {
      final res = await http.get(Uri.parse('$baseUrl/health'), headers: kBackendHeaders).timeout(_timeout);
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// GET helper that maps connection failures to a friendly offline message,
  /// so screens show "can't reach the backend" instead of a raw exception.
  Future<http.Response> _get(String path) async {
    try {
      return await http.get(Uri.parse('$baseUrl$path'), headers: kBackendHeaders).timeout(_timeout);
    } on TimeoutException {
      throw ApiException("Can't reach the backend — it timed out. Check it's running and the URL in Settings.");
    } on SocketException {
      throw ApiException("Can't reach the backend. Check it's running and the URL in Settings.");
    } on http.ClientException {
      throw ApiException("Can't reach the backend. Check it's running and the URL in Settings.");
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
          headers: {'Content-Type': 'application/json', ...kBackendHeaders},
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
      ..headers.addAll(kBackendHeaders)
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
        .post(Uri.parse('$baseUrl/members/$name/enroll'), headers: kBackendHeaders)
        .timeout(const Duration(seconds: 90));
    if (res.statusCode != 200) {
      throw ApiException(_detailOf(res) ?? 'Enrollment failed (HTTP ${res.statusCode}).');
    }
    return (jsonDecode(res.body) as Map<String, dynamic>)['embedding_count'] as int;
  }

  /// Remove a member (embeddings + photos).
  Future<void> deleteMember(String name) async {
    final res = await http
        .delete(Uri.parse('$baseUrl/members/$name'), headers: kBackendHeaders)
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
    if (code == 503) {
      return 'Vision pipeline not running (camera offline?). Start the backend and camera.';
    }
    return 'Failed to load $what (HTTP $code).';
  }
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}
