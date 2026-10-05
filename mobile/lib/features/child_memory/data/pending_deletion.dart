/// Finishing an account deletion the app did not see through (MOBILE_API §10;
/// PR #36 reviews).
///
/// Two ways a deletion can be left half-done on the phone:
///   * the server's answer never arrived ([kAccountDeletionRequested]) — the
///     account may or may not be gone. The same DELETE is sent again with the
///     token it first carried ([settlePendingAccountDeletion], after the first
///     frame: it needs the network, and the app keeps working meanwhile);
///   * the server answered, but the app was killed before this install had
///     fully started over or the phone was cleared
///     ([kAccountDeletionConfirmed]) — finished locally, before anything reads
///     the onboarding state ([completePendingAccountDeletion]).
library;

import '../../../api/tg_client.dart';
import 'local_wipe.dart';
import 'memory_models.dart';

/// Before `runApp` — local only, never the network: a confirmed deletion
/// whose clearing was cut short is finished. The install starts over again
/// if the erased id is still held anywhere (killed inside the start-over),
/// then the phone is cleared. Returns true when the phone was cleared. A
/// deletion still waiting for its answer is left to
/// [settlePendingAccountDeletion]: it must not hold the first frame.
Future<bool> completePendingAccountDeletion({
  TgClient? client,
  Future<void> Function()? wipe,
}) async {
  final c = client ?? TgClient.shared;
  if (await c.accountDeletionState() != kAccountDeletionConfirmed) return false;
  await c.startOverAfterAccountDeletion();
  // Without the push token's renewal — the network must not hold the first
  // frame; main() runs it after (renewPushTokenAfterWipe).
  await (wipe ??
      () => wipeLocalDataAfterAccountDeletion(pushTokenLater: true))();
  return true;
}

/// What sending a lost DELETE again found.
enum PendingDeletion {
  /// No deletion was waiting for its answer.
  none,

  /// The account is gone; this install has started over. The phone still has
  /// to be cleared (the settled `result` says what to show).
  deleted,

  /// The server refused it: nothing was deleted, and nothing is pending.
  notDeleted,

  /// Still no answer: kept for the next launch or the screen's "check again".
  unknown,
}

typedef PendingDeletionSettled = ({
  PendingDeletion outcome,
  AccountDeletionResult? result,
});

/// After the first frame: settle a deletion whose answer was lost by sending
/// the same DELETE again (TgClient.settleAccountDeletion). No network when
/// nothing is pending — every launch but one.
Future<PendingDeletionSettled> settlePendingAccountDeletion({
  TgClient? client,
}) async {
  final c = client ?? TgClient.shared;
  if (await c.accountDeletionState() != kAccountDeletionRequested) {
    return (outcome: PendingDeletion.none, result: null);
  }
  try {
    final body = await c.settleAccountDeletion();
    if (body == null) return (outcome: PendingDeletion.none, result: null);
    return (
      outcome: PendingDeletion.deleted,
      result: AccountDeletionResult.fromJson(body),
    );
  } on TgApiError catch (e) {
    if (e.code == 'account_deletion_unconfirmed') {
      return (outcome: PendingDeletion.unknown, result: null);
    }
    return (outcome: PendingDeletion.notDeleted, result: null);
  } catch (_) {
    return (outcome: PendingDeletion.unknown, result: null);
  }
}
