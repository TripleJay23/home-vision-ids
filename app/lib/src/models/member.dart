/// One enrolled member from `GET /members` (mirrors MemberOut).
class Member {
  final String name;
  final int embeddingCount;
  final String? enrolledAt;

  Member({required this.name, required this.embeddingCount, this.enrolledAt});

  factory Member.fromJson(Map<String, dynamic> json) => Member(
        name: json['name'] as String,
        embeddingCount: json['embedding_count'] as int,
        enrolledAt: json['enrolled_at'] as String?,
      );
}
