/// Files the app writes for a moment and that must never reach a backup: a
/// feedback voice note on its way to the server, an agreement image on its way
/// to the share sheet.
///
/// They live in one folder of the documents directory, [localOnlyFolderName],
/// which backup_rules.xml (Android ≤ 11) and data_extraction_rules.xml
/// (Android 12+, both cloud backup and device transfer) exclude. An account
/// deletion clears the phone, but the phone's Auto Backup keeps what was there
/// — a parent's recorded voice, a picture with the child's name in its file
/// name — and a restore would put it back (PR #36 review). Wildcards are not
/// possible in those rules, so the files cannot stay loose in the documents
/// directory, where older builds wrote them.
library;

import 'dart:io';

import 'package:path_provider/path_provider.dart';

/// The folder, under path_provider's documents directory — on Android
/// `<data dir>/app_flutter/local_only`, the "root" domain of the backup rules.
const String localOnlyFolderName = 'local_only';

/// The folder for files that never leave this phone, created when missing.
Future<Directory> localOnlyDirectory() async {
  final docs = await getApplicationDocumentsDirectory();
  final dir = Directory('${docs.path}/$localOnlyFolderName');
  await dir.create(recursive: true);
  return dir;
}

/// What older builds left loose in the documents directory: a voice note
/// (`feedback_<ms>.m4a`, already sent or abandoned) and an agreement image
/// (`agreement_<name>.png`, re-made on every share).
final RegExp _strayFile = RegExp(r'^(feedback_\d+\.m4a|agreement_.+\.png)$');

/// Remove those loose files, so no further backup carries them. Best effort;
/// [documents] for tests.
Future<void> removeStrayPrivateFiles({Directory? documents}) async {
  try {
    final docs = documents ?? await getApplicationDocumentsDirectory();
    if (!await docs.exists()) return;
    await for (final entity in docs.list(followLinks: false)) {
      if (entity is! File) continue;
      if (!_strayFile.hasMatch(entity.uri.pathSegments.last)) continue;
      try {
        await entity.delete();
      } catch (_) {}
    }
  } catch (_) {}
}
