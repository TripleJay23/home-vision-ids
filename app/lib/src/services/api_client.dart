import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/alert.dart';
import '../models/member.dart';

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
      final res = await http.get(Uri.parse('$baseUrl/health')).timeout(_timeout);
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<List<Alert>> getAlerts({int limit = 20}) async {
    final res = await http.get(Uri.parse('$baseUrl/alerts?limit=$limit')).timeout(_timeout);
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
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'token': token}),
        )
        .timeout(_timeout);
    if (res.statusCode != 200) {
      throw ApiException('Device registration failed (HTTP ${res.statusCode}).');
    }
  }

  Future<List<Member>> getMembers() async {
    final res = await http.get(Uri.parse('$baseUrl/members')).timeout(_timeout);
    if (res.statusCode != 200) {
      throw ApiException(_describe('members', res.statusCode));
    }
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    final list = (body['members'] as List).cast<Map<String, dynamic>>();
    return list.map(Member.fromJson).toList();
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
