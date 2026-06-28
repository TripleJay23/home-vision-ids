import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

/// Caches alert snapshot JPEGs on the device, keyed by `alertId`.
///
/// The backend serves snapshots only from an in-memory ring buffer
/// (`/alerts/<id>/snapshot`), so they disappear on restart and are unreachable
/// offline. Caching the bytes the first time an alert loads keeps the evidence
/// available for "Save to gallery" even when the backend is gone.
class SnapshotCache {
  Directory? _dir;

  Future<Directory> _ensureDir() async {
    if (_dir != null) return _dir!;
    final base = await getApplicationDocumentsDirectory();
    final dir = Directory('${base.path}/alert_snapshots');
    if (!await dir.exists()) await dir.create(recursive: true);
    return _dir = dir;
  }

  File _fileFor(Directory dir, String alertId) {
    final safe = alertId.replaceAll(RegExp(r'[^A-Za-z0-9_.-]'), '_');
    return File('${dir.path}/$safe.jpg');
  }

  /// Bytes for a previously-cached snapshot, or null if not cached.
  Future<Uint8List?> read(String alertId) async {
    try {
      final f = _fileFor(await _ensureDir(), alertId);
      return await f.exists() ? await f.readAsBytes() : null;
    } catch (_) {
      return null;
    }
  }

  /// Persist snapshot bytes for [alertId]. Best-effort; ignores write failures.
  Future<void> write(String alertId, Uint8List bytes) async {
    try {
      await _fileFor(await _ensureDir(), alertId).writeAsBytes(bytes, flush: true);
    } catch (_) {/* cache is best-effort */}
  }
}
