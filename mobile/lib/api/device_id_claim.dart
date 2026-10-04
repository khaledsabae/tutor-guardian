/// The one-time claim of the install's device id, shared by every isolate.
library;

import 'dart:async';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// Decides, once per install, which candidate becomes the device id — no
/// matter how many isolates are asking at the same moment.
///
/// Why an in-memory single-flight is not enough: on 2026-10-04 the app was
/// found running `main()` in TWO Flutter engines in one process (the
/// `audio_service` plugin started the second one; see pubspec.yaml). Each
/// engine is its own isolate with its own memory, so each found the keystore
/// empty on a fresh install and minted its own id — the "device twin" that
/// made ~40% of new families come back childless after a restart. That engine
/// is gone, and this keeps the identity safe from the next one, whatever
/// starts it.
///
/// `File.create(exclusive: true)` is O_CREAT|O_EXCL: atomic across isolates and
/// processes, so exactly one candidate ever wins and every loser reads the
/// winner's id. The file is the arbiter, not the store — the keystore and the
/// SharedPreferences backup still hold the id; this is consulted only when
/// both are empty.
class DeviceIdClaim {
  DeviceIdClaim(this._directory, {this.fileName = 'tg_device_id.claim'});

  /// The app's cache directory on Android and iOS; nowhere elsewhere.
  ///
  /// Cache, not support or documents: it is never part of a cloud backup, so
  /// restoring a backup on a new phone cannot clone this install's id onto
  /// it. If the OS clears it later nothing is lost — by then the id is in the
  /// keystore and the backup. Hosts other than a phone (the unit-test VM)
  /// get no claim, so a test never shares an id through the real disk.
  factory DeviceIdClaim.inAppCache() => DeviceIdClaim(() async {
        if (!(Platform.isAndroid || Platform.isIOS)) return null;
        return getApplicationCacheDirectory();
      });

  final Future<Directory?> Function() _directory;
  final String fileName;

  /// The winner never needs more than one write after its create, so a loser
  /// that still sees an empty file after this long is looking at a claim
  /// whose writer died in between — not worth blocking startup on.
  static const _readTimeout = Duration(seconds: 2);
  static const _readPoll = Duration(milliseconds: 10);

  /// Claim [candidate] as the install's device id, or return the id that is
  /// already claimed. Null when no claim can be made (no directory, I/O
  /// error): the caller then uses its own candidate, as before this existed.
  Future<String?> claim(String candidate) async {
    try {
      final file = await _file();
      if (file == null) return null;
      try {
        await file.create(exclusive: true);
      } on FileSystemException {
        if (!await file.exists()) return null; // not "already claimed"
        return await _readClaimed(file);
      }
      await file.writeAsString(candidate, flush: true);
      return candidate;
    } catch (_) {
      return null;
    }
  }

  /// Point the claim at [id] — the server re-attached this install to the
  /// family's device, and a later keystore loss must not resurrect the old id.
  Future<void> replace(String id) async {
    try {
      final file = await _file();
      if (file == null) return;
      await file.writeAsString(id, flush: true);
    } catch (_) {
      // Best effort: the keystore and the backup already hold [id].
    }
  }

  Future<File?> _file() async {
    final dir = await _directory();
    if (dir == null) return null;
    if (!await dir.exists()) await dir.create(recursive: true);
    return File('${dir.path}${Platform.pathSeparator}$fileName');
  }

  Future<String?> _readClaimed(File file) async {
    final deadline = DateTime.now().add(_readTimeout);
    while (true) {
      final id = (await file.readAsString()).trim();
      if (id.isNotEmpty && id.length <= 200 && !id.contains('\n')) return id;
      if (DateTime.now().isAfter(deadline)) return null;
      await Future<void>.delayed(_readPoll);
    }
  }
}
