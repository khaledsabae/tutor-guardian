/// «المربّي يعرف ابنك» over [TgClient] — typed, and with the proof rule
/// applied per call (MOBILE_API §9.0).
///
/// Protected calls go through [TgClient.withDeviceProof]: a
/// `device_proof_required` runs the challenge once and retries once. Two kinds
/// of call deliberately do not:
///   * the ones §9.0 says never need a proof (the settings, switching memory
///     off, the weekly plan);
///   * the Today follow-up list ([dueFollowups]) — a card that hides itself
///     must not start a challenge; the launch's background proof does, and the
///     card refetches when it lands.
///
/// "Not supported" is a first-class answer: the production server that
/// predates these routes answers FastAPI's bare 404, and every feature here
/// hides itself on it rather than showing an error ([TgApiError.isMissingEndpoint]).
library;

import '../../../api/tg_client.dart';
import 'memory_models.dart';

class MemoryRepository {
  MemoryRepository(this._client);

  final TgClient _client;

  /// The device's UTC offset — the follow-up push learns the family's evening
  /// from it, and the weekly plan the family's Monday.
  static int tzOffsetMinutes() => DateTime.now().timeZoneOffset.inMinutes;

  /// The memory switch, or null on a server without memory.
  Future<MemorySettings?> settings() async {
    try {
      return MemorySettings.fromJson(await _client.getMemorySettings());
    } on TgApiError catch (e) {
      if (e.isMissingEndpoint) return null;
      rethrow;
    }
  }

  /// Switching off never needs a proof — stopping must always work. Switching
  /// on does.
  Future<MemorySettings> setEnabled(bool enabled) async {
    final json = enabled
        ? await _client.withDeviceProof(
            () => _client.putMemorySettings(enabled: true))
        : await _client.putMemorySettings(enabled: false);
    return MemorySettings.fromJson(json);
  }

  Future<ChildMemory> facts(int childId) async => ChildMemory.fromJson(
      await _client.withDeviceProof(() => _client.getChildMemory(childId)));

  Future<MemoryFact> addFact(int childId,
          {required String category, required String fact}) async =>
      MemoryFact.fromJson(await _client.withDeviceProof(() =>
          _client.addChildFact(childId, category: category, fact: fact)));

  Future<MemoryFact> updateFact(int childId, int factId,
          {String? fact, String? category, String? status}) async =>
      MemoryFact.fromJson(await _client.withDeviceProof(() =>
          _client.patchChildFact(childId, factId,
              fact: fact, category: category, status: status)));

  Future<void> deleteFact(int childId, int factId) => _client
      .withDeviceProof(() => _client.deleteChildFact(childId, factId));

  Future<void> forgetChild(int childId) =>
      _client.withDeviceProof(() => _client.deleteChildMemory(childId));

  /// Due follow-ups for the Today card — no proof is started from here.
  /// Null when there is nothing the card can show: an older server, a
  /// session not proven yet, a pause, or any failure.
  Future<List<Followup>?> dueFollowups() async {
    try {
      final json = await _client.getDueFollowups(
          tzOffsetMinutes: tzOffsetMinutes());
      return [
        for (final f in (json['followups'] as List? ?? const []))
          if (f is Map) Followup.fromJson(Map<String, dynamic>.from(f)),
      ];
    } catch (_) {
      return null;
    }
  }

  Future<Followup> followup(int followupId) async {
    final json = await _client
        .withDeviceProof(() => _client.getFollowup(followupId));
    return Followup.fromJson(
        Map<String, dynamic>.from(json['followup'] as Map? ?? const {}));
  }

  Future<FollowupAnswer> answer(int followupId,
          {required String outcome, String? note}) async =>
      FollowupAnswer.fromJson(await _client.withDeviceProof(() =>
          _client.answerFollowup(followupId, outcome: outcome, note: note)));

  Future<Followup> dismiss(int followupId) async {
    final json = await _client
        .withDeviceProof(() => _client.dismissFollowup(followupId));
    return Followup.fromJson(
        Map<String, dynamic>.from(json['followup'] as Map? ?? const {}));
  }

  /// This week's plan, or null when there is none to show (older server,
  /// any failure, or a plan with no focus/actions).
  Future<WeeklyPlan?> weeklyPlan(int childId, {required String lang}) async {
    try {
      final plan = WeeklyPlan.fromJson(await _client.getWeeklyPlan(childId,
          lang: lang, tzOffsetMinutes: tzOffsetMinutes()));
      return plan.isUsable ? plan : null;
    } catch (_) {
      return null;
    }
  }

  /// Memory of every child of this device (§9.6).
  Future<void> eraseAll() =>
      _client.withDeviceProof(() => _client.deleteAllMemory());

  /// The proof and pause state, or null on a server without device proof.
  Future<DeviceProofStatus?> proofStatus() async {
    try {
      return DeviceProofStatus.fromJson(await _client.getDeviceProofStatus());
    } on TgApiError catch (e) {
      if (e.isMissingEndpoint) return null;
      rethrow;
    }
  }

  /// Account deletion (§10). On success the client has already become a new
  /// device; the caller wipes what is left on the phone.
  Future<AccountDeletionResult> deleteAccount() async =>
      AccountDeletionResult.fromJson(
          await _client.withDeviceProof(() => _client.deleteAccount()));
}
