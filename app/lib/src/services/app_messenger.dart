import 'package:flutter/material.dart';

/// Global ScaffoldMessenger key so non-widget code (e.g. push handlers) can
/// show SnackBars without a BuildContext.
final appMessengerKey = GlobalKey<ScaffoldMessengerState>();
