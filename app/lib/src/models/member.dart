/// One enrolled member from `GET /members` (mirrors MemberOut).
class Member {
  final String name;
  final int embeddingCount;
  final String? enrolledAt;

  /// Enrollment lifecycle: "enrolled" | "enrolling" | "failed". A member whose
  /// background build is still running reports "enrolling"; the UI shows a
  /// spinner and polls until it flips to "enrolled".
  final String status;
  final String? error;

  Member({
    required this.name,
    required this.embeddingCount,
    this.enrolledAt,
    this.status = 'enrolled',
    this.error,
  });

  bool get isEnrolling => status == 'enrolling';
  bool get isFailed => status == 'failed';

  factory Member.fromJson(Map<String, dynamic> json) => Member(
        name: json['name'] as String,
        embeddingCount: json['embedding_count'] as int,
        enrolledAt: json['enrolled_at'] as String?,
        status: (json['status'] as String?) ?? 'enrolled',
        error: json['error'] as String?,
      );

  /// Inverse of [Member.fromJson] — same keys, for the offline cache.
  Map<String, dynamic> toJson() => {
        'name': name,
        'embedding_count': embeddingCount,
        'enrolled_at': enrolledAt,
        'status': status,
        'error': error,
      };
}
