/// Phase 7 repository — list / update / reset on /api/children.
library;

import '../../../api/tg_client.dart';
import 'progress_models.dart';

class SettingsRepository {
  SettingsRepository(this._client);

  final TgClient _client;

  /// `GET /api/children` — returns the typed [ChildListEnvelope].
  Future<ChildListEnvelope> listChildren() async {
    final json = await _client.listChildren();
    return ChildListEnvelope.fromJson(json);
  }

  /// `PATCH /api/children/{id}` — returns the updated [ChildProfile].
  /// `name` and `ageGroup` are always sent (we treat null as "no
  /// change" and pass the existing value through from the caller).
  Future<ChildProfile> updateChild({
    required int childId,
    required String name,
    required String ageGroup,
    String? gender,
    String? avatarEmoji,
  }) async {
    final json = await _client.updateChild(
      childId: childId,
      name: name,
      ageGroup: ageGroup,
      gender: gender,
      avatarEmoji: avatarEmoji,
    );
    return ChildProfile.fromJson(json);
  }

  /// `DELETE /api/children/{id}/progress` — idempotent.
  Future<int> resetProgress(int childId) async {
    final json = await _client.resetChildProgress(childId);
    return (json['deleted'] as num?)?.toInt() ?? 0;
  }
}
