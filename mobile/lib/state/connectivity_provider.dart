/// Streams the device's online/offline status.
///
/// Exposes a single Riverpod provider that the UI can `ref.watch` to
/// render an "غير متصل" banner. The first value is emitted on listen,
/// so consumers don't need a separate "loading" state.
library;

import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// `true` if the device has at least one active network interface and we
/// are not in the "none" state. Updated as the OS reports changes.
final connectivityProvider = StreamProvider<bool>((ref) {
  final c = Connectivity();
  // Seed with the current state, then merge with the change stream.
  final controller = StreamController<bool>();
  unawaited(_seed(c, controller));
  final sub = c.onConnectivityChanged.listen((results) {
    final online = !results.contains(ConnectivityResult.none);
    controller.add(online);
  });
  ref.onDispose(() {
    sub.cancel();
    controller.close();
  });
  return controller.stream;
});

Future<void> _seed(Connectivity c, StreamController<bool> controller) async {
  try {
    final initial = await c.checkConnectivity();
    controller.add(!initial.contains(ConnectivityResult.none));
  } catch (_) {
    // Connectivity check failed — assume online so the UI doesn't get
    // stuck in a permanent "offline" state when the plugin is missing
    // permissions.
    controller.add(true);
  }
}
