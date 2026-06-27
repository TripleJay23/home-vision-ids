import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/providers.dart';

/// Guided poses — one capture each. Variety across angles AND distances gives
/// the recogniser reference embeddings that match what a (often distant,
/// top-corner) camera actually sees, not just close-up frontal shots.
const List<(String, String)> _poses = [
  ('Look STRAIGHT at the camera', 'straight'),
  ('Turn slightly LEFT', 'left'),
  ('Turn slightly RIGHT', 'right'),
  ('Look UP (like at a high corner camera)', 'up'),
  ('Look slightly DOWN', 'down'),
  ('Step BACK a few steps (mid distance)', 'mid'),
  ('Step BACK further away (far)', 'far'),
  ('Any angle you like', 'free'),
];

/// Shots taken per pose on a single "Capture" tap (a quick burst). 8 poses ×
/// this = the ~32 reference photos the recogniser wants for robustness, without
/// 32 taps.
const int _shotsPerPose = 4;

enum _Phase { naming, capturing, enrolling, done }

/// In-app member enrollment using the device camera: enter a name, walk through
/// the guided poses tapping Capture, then the backend builds the embeddings.
class EnrollMemberScreen extends ConsumerStatefulWidget {
  const EnrollMemberScreen({super.key});

  @override
  ConsumerState<EnrollMemberScreen> createState() => _EnrollMemberScreenState();
}

class _EnrollMemberScreenState extends ConsumerState<EnrollMemberScreen> {
  final _nameController = TextEditingController();

  _Phase _phase = _Phase.naming;
  List<CameraDescription> _cameras = const [];
  CameraController? _controller;
  int _camIndex = 0;
  int _poseIndex = 0;
  bool _busy = false;
  String? _error;
  String? _status; // transient "Capturing 2/4…" during a burst
  String _name = '';
  int _enrolledCount = 0;

  @override
  void dispose() {
    _controller?.dispose();
    _nameController.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    final name = _nameController.text.trim().toLowerCase();
    if (name.isEmpty || !RegExp(r'^[a-z0-9_-]+$').hasMatch(name)) {
      setState(() => _error = 'Name must be letters / digits / _ / - only.');
      return;
    }
    setState(() {
      _error = null;
      _busy = true;
    });
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) throw 'No camera found on this device.';
      _camIndex = _cameras.indexWhere((c) => c.lensDirection == CameraLensDirection.back);
      if (_camIndex < 0) _camIndex = 0;
      await _initController();
      setState(() {
        _name = name;
        _phase = _Phase.capturing;
        _busy = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Camera unavailable: $e';
        _busy = false;
      });
    }
  }

  Future<void> _initController() async {
    await _controller?.dispose();
    final ctrl = CameraController(_cameras[_camIndex], ResolutionPreset.high, enableAudio: false);
    await ctrl.initialize();
    if (!mounted) {
      await ctrl.dispose();
      return;
    }
    setState(() => _controller = ctrl);
  }

  Future<void> _flip() async {
    if (_cameras.length < 2 || _busy) return;
    _camIndex = (_camIndex + 1) % _cameras.length;
    setState(() => _busy = true);
    await _initController();
    setState(() => _busy = false);
  }

  Future<void> _capture() async {
    final ctrl = _controller;
    if (ctrl == null || !ctrl.value.isInitialized || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final (_, tag) = _poses[_poseIndex];
      final api = ref.read(apiClientProvider);
      // Burst: a few quick shots per pose for more reference embeddings.
      for (var i = 0; i < _shotsPerPose; i++) {
        setState(() => _status = 'Capturing ${i + 1}/$_shotsPerPose…');
        final shot = await ctrl.takePicture();
        await api.uploadPhoto(_name, tag, await shot.readAsBytes());
        if (i < _shotsPerPose - 1) {
          await Future.delayed(const Duration(milliseconds: 300));
        }
      }
      setState(() => _status = null);
      if (_poseIndex + 1 >= _poses.length) {
        await _enroll();
      } else {
        setState(() {
          _poseIndex++;
          _busy = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Capture failed: $e';
        _status = null;
        _busy = false;
      });
    }
  }

  Future<void> _enroll() async {
    setState(() {
      _phase = _Phase.enrolling;
      _busy = true;
    });
    try {
      final count = await ref.read(apiClientProvider).enrollMember(_name);
      await _controller?.dispose();
      _controller = null;
      ref.invalidate(membersProvider);
      setState(() {
        _enrolledCount = count;
        _phase = _Phase.done;
        _busy = false;
      });
    } catch (e) {
      // Enrollment failed (e.g. no face found) — let them re-capture.
      setState(() {
        _error = '$e';
        _phase = _Phase.capturing;
        _poseIndex = 0;
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Enroll member')),
      body: switch (_phase) {
        _Phase.naming => _buildNaming(),
        _Phase.capturing => _buildCapturing(),
        _Phase.enrolling => _buildEnrolling(),
        _Phase.done => _buildDone(),
      },
    );
  }

  Widget _buildNaming() {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: 8),
          Text('Add a household member', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          Text(
            'Walk through ${_poses.length} poses — different angles AND distances '
            '(including stepping back). Each tap takes a quick burst of $_shotsPerPose '
            'shots (~${_poses.length * _shotsPerPose} photos total) for accuracy. '
            'Tip: enroll where the security camera will see them.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _nameController,
            autocorrect: false,
            textCapitalization: TextCapitalization.none,
            decoration: const InputDecoration(
              labelText: 'Member name',
              hintText: 'e.g. mama',
              border: OutlineInputBorder(),
              prefixIcon: Icon(Icons.person_add_alt),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 10),
            Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ],
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _busy ? null : _start,
            icon: _busy
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.camera_alt_outlined),
            label: const Text('Start camera'),
          ),
        ],
      ),
    );
  }

  Widget _buildCapturing() {
    final ctrl = _controller;
    final ready = ctrl != null && ctrl.value.isInitialized;
    final (prompt, _) = _poses[_poseIndex];
    return Column(
      children: [
        Expanded(
          child: Container(
            color: Colors.black,
            width: double.infinity,
            child: Stack(
              alignment: Alignment.center,
              children: [
                if (ready) CameraPreview(ctrl) else const CircularProgressIndicator(),
                Positioned(
                  top: 16,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(20)),
                    child: Text(prompt,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 16)),
                  ),
                ),
              ],
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              if (_error != null) ...[
                Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                const SizedBox(height: 8),
              ],
              Text(
                _status ?? 'Pose ${_poseIndex + 1} of ${_poses.length}  ·  $_shotsPerPose shots each',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 8),
              LinearProgressIndicator(value: _poseIndex / _poses.length),
              const SizedBox(height: 14),
              Row(
                children: [
                  IconButton.filledTonal(
                    onPressed: _cameras.length > 1 && !_busy ? _flip : null,
                    icon: const Icon(Icons.cameraswitch_outlined),
                    tooltip: 'Flip camera',
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: (ready && !_busy) ? _capture : null,
                      icon: _busy
                          ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.camera),
                      label: Text(_poseIndex + 1 >= _poses.length ? 'Capture & finish' : 'Capture'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildEnrolling() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text('Building face profile for "$_name"…', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Text('Running detection + recognition on your photos.',
              style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }

  Widget _buildDone() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_circle, size: 64, color: Colors.green.shade600),
            const SizedBox(height: 16),
            Text('"$_name" enrolled', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text('$_enrolledCount face samples added.', style: Theme.of(context).textTheme.bodyMedium),
            const SizedBox(height: 24),
            FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Done')),
          ],
        ),
      ),
    );
  }
}
