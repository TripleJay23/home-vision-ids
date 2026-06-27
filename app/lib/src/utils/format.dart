import 'package:flutter/material.dart';

/// "2m ago"-style relative time from an ISO-8601 timestamp. Falls back to the
/// raw string if it can't be parsed.
String timeAgo(String iso) {
  final dt = DateTime.tryParse(iso);
  if (dt == null) return iso;
  final d = DateTime.now().difference(dt);
  if (d.inSeconds < 45) return 'just now';
  if (d.inMinutes < 60) return '${d.inMinutes}m ago';
  if (d.inHours < 24) return '${d.inHours}h ago';
  if (d.inDays < 7) return '${d.inDays}d ago';
  return iso.split('T').first; // date only for anything older
}

/// Deterministic, pleasant colour for a name — gives each member a stable
/// avatar colour without needing to store one.
Color colorForName(String name) {
  const palette = <Color>[
    Color(0xFF1565C0), // blue
    Color(0xFF00897B), // teal
    Color(0xFF6A1B9A), // purple
    Color(0xFFD84315), // deep orange
    Color(0xFF2E7D32), // green
    Color(0xFFAD1457), // pink
  ];
  if (name.isEmpty) return palette.first;
  final h = name.codeUnits.fold<int>(0, (acc, c) => acc + c);
  return palette[h % palette.length];
}
