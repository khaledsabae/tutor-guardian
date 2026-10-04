/// Finishing an account deletion the app did not see through (MOBILE_API §10;
/// PR #36 review, item 4).
///
/// Two ways a deletion can be left half-done on the phone:
///   * the server's answer never arrived ([kAccountDeletionRequested]) — the
///     account may or may not be gone; the old token tells: 401 means gone;
///   * the server answered, but the app was killed before the phone was
///     cleared ([kAccountDeletionConfirmed]).
/// Run at launch, BEFORE anything can mint a session or read the onboarding
/// state, so a deleted account neither comes back to life on the server (a
/// session minted for its id) nor on the screen (its cached children).
library;

import 'dart:async';

import '../../../api/tg_client.dart';
import 'local_wipe.dart';

/// Settle a deletion left half-done. Returns true when the phone was cleared
/// (the app continues as a fresh install). No-op — and no network — when no
/// deletion is recorded, which is every launch but one.
Future<bool> completePendingAccountDeletion({
  TgClient? client,
  Future<void> Function()? wipe,
  Duration probeTimeout = const Duration(seconds: 8),
}) async {
  final c = client ?? TgClient.shared;
  final state = await c.accountDeletionState();
  if (state == null) return false;
  if (state == kAccountDeletionRequested) {
    final deleted = await c
        .probeAccountDeleted()
        .timeout(probeTimeout, onTimeout: () => null);
    if (deleted == false) {
      // The old token still works: nothing was deleted.
      await c.clearAccountDeletionState();
      return false;
    }
    // No answer: leave it recorded. Minting stays blocked (TgClient), and the
    // next launch — or the deletion screen's "check again" — asks again.
    if (deleted == null) return false;
    await c.startOverAfterAccountDeletion();
  }
  await (wipe ?? wipeLocalDataAfterAccountDeletion)();
  return true;
}
