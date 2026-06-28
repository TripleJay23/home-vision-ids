/// One alert from `GET /alerts` (mirrors api/schemas/alert.py: AlertOut).
class Alert {
  final String alertId;
  final int trackId;
  final String createdAt;
  final String reason;
  final double? distance;

  /// API-relative path to the snapshot image, e.g. `/alerts/<id>/snapshot`.
  /// Null when no snapshot was saved. Prefix with the backend base URL to fetch.
  final String? snapshotUrl;

  Alert({
    required this.alertId,
    required this.trackId,
    required this.createdAt,
    required this.reason,
    this.distance,
    this.snapshotUrl,
  });

  factory Alert.fromJson(Map<String, dynamic> json) => Alert(
        alertId: json['alert_id'] as String,
        trackId: json['track_id'] as int,
        createdAt: json['created_at'] as String,
        reason: json['reason'] as String,
        distance: (json['distance'] as num?)?.toDouble(),
        snapshotUrl: json['snapshot_url'] as String?,
      );

  /// Inverse of [Alert.fromJson] — same snake_case keys, so a list round-trips
  /// through the local offline cache (see providers.dart).
  Map<String, dynamic> toJson() => {
        'alert_id': alertId,
        'track_id': trackId,
        'created_at': createdAt,
        'reason': reason,
        'distance': distance,
        'snapshot_url': snapshotUrl,
      };
}
