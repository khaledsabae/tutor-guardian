/// Covenants — the one thing coins buy, and it happens off the screen.
///
/// A covenant is a real reward a parent has agreed to: a trip to the park, an
/// extra half hour of playing together, choosing Friday's dinner. The child
/// redeems coins against it in the app; the parent hands it over in the world.
/// That second half is the entire point, so it is tracked rather than assumed
/// — a redeemed reward that was never delivered is a promise the app helped
/// break, and [overdueDeliveries] exists to say so out loud.
///
/// Rewards are per child. They used to be one shared list under a single key,
/// which meant a family with two children had one set of prices and no way to
/// tell whose reward had been redeemed. The old list migrates to the first
/// child that opens the screen rather than being dropped.
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

class Covenant {
  final String id;
  final String title;
  final int cost;
  final bool isRedeemed;
  final bool isDelivered;
  final String? redeemedAt;

  const Covenant({
    required this.id,
    required this.title,
    required this.cost,
    this.isRedeemed = false,
    this.isDelivered = false,
    this.redeemedAt,
  });

  /// Redeemed, not yet handed over, and long enough ago that the child has
  /// noticed. Seven days is the threshold the reminder uses.
  bool isOverdue({int afterDays = 7, DateTime? now}) {
    if (!isRedeemed || isDelivered) return false;
    final at = DateTime.tryParse(redeemedAt ?? '');
    if (at == null) return false;
    return (now ?? DateTime.now()).difference(at).inDays >= afterDays;
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'cost': cost,
        'isRedeemed': isRedeemed,
        'isDelivered': isDelivered,
        'redeemedAt': redeemedAt,
      };

  factory Covenant.fromJson(Map<String, dynamic> json) => Covenant(
        id: json['id'] as String,
        title: json['title'] as String,
        cost: json['cost'] as int,
        isRedeemed: json['isRedeemed'] as bool? ?? false,
        isDelivered: json['isDelivered'] as bool? ?? false,
        redeemedAt: json['redeemedAt'] as String?,
      );

  Covenant copyWith({
    bool? isRedeemed,
    bool? isDelivered,
    String? redeemedAt,
  }) {
    return Covenant(
      id: id,
      title: title,
      cost: cost,
      isRedeemed: isRedeemed ?? this.isRedeemed,
      isDelivered: isDelivered ?? this.isDelivered,
      redeemedAt: redeemedAt ?? this.redeemedAt,
    );
  }
}

class CovenantService {
  CovenantService._();
  static final CovenantService instance = CovenantService._();

  /// The pre-split key: one list for the whole family.
  static const _kLegacy = 'covenant.list';

  static String _key(int childId) => 'covenant.list.$childId';

  final List<Covenant> _defaults = const [
    Covenant(id: 'def_1', title: 'شراء مثلجات لذيذة 🍦', cost: 30),
    Covenant(id: 'def_2', title: 'نصف ساعة لعب إضافية 🎮', cost: 50),
    Covenant(id: 'def_3', title: 'رحلة عائلية مميزة للحديقة 🌳', cost: 100),
  ];

  List<Covenant> _decode(String raw) {
    final list = jsonDecode(raw) as List;
    return list.map((e) => Covenant.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Covenant>> load(int childId) async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_key(childId));
    if (raw != null) {
      try {
        return _decode(raw);
      } catch (_) {
        return List.of(_defaults);
      }
    }

    // First read for this child. Adopt the family's old shared list if one is
    // still there — those are rewards a parent typed and a child may already
    // have saved for — otherwise start from the defaults.
    final legacy = p.getString(_kLegacy);
    if (legacy != null) {
      try {
        final adopted = _decode(legacy);
        await save(childId, adopted);
        await p.remove(_kLegacy);
        return adopted;
      } catch (_) {
        // fall through to defaults
      }
    }
    await save(childId, _defaults);
    // A copy, not the const list itself: `add` mutates what `load` returned,
    // and handing back an unmodifiable list makes the first added reward throw.
    return List.of(_defaults);
  }

  Future<void> save(int childId, List<Covenant> list) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_key(childId), jsonEncode(list.map((e) => e.toJson()).toList()));
  }

  Future<void> add(int childId, String title, int cost) async {
    final list = await load(childId);
    list.add(Covenant(
      id: 'cov_${DateTime.now().millisecondsSinceEpoch}',
      title: title,
      cost: cost,
    ));
    await save(childId, list);
  }

  Future<bool> redeem(int childId, String id) async {
    final list = await load(childId);
    final idx = list.indexWhere((e) => e.id == id);
    if (idx == -1 || list[idx].isRedeemed) return false;
    list[idx] = list[idx].copyWith(
      isRedeemed: true,
      redeemedAt: DateTime.now().toIso8601String(),
    );
    await save(childId, list);
    return true;
  }

  Future<void> deliver(int childId, String id) async {
    final list = await load(childId);
    final idx = list.indexWhere((e) => e.id == id);
    if (idx == -1) return;
    list[idx] = list[idx].copyWith(isDelivered: true);
    await save(childId, list);
  }

  Future<void> delete(int childId, String id) async {
    final list = await load(childId);
    list.removeWhere((e) => e.id == id);
    await save(childId, list);
  }

  /// Rewards the child paid for and is still waiting on. The screen surfaces
  /// these to the parent; an app that lets a promise go quiet is worse than
  /// one that never offered the reward.
  Future<List<Covenant>> overdueDeliveries(int childId, {int afterDays = 7}) async {
    final list = await load(childId);
    return list.where((c) => c.isOverdue(afterDays: afterDays)).toList();
  }

  /// How many rewards actually reached the child this month.
  ///
  /// This is the number worth showing a parent — "three rewards delivered"
  /// says something about the month, where a coin balance says only that the
  /// app was opened.
  Future<int> deliveredThisMonth(int childId, {DateTime? now}) async {
    final list = await load(childId);
    final ref = now ?? DateTime.now();
    return list.where((c) {
      if (!c.isDelivered) return false;
      final at = DateTime.tryParse(c.redeemedAt ?? '');
      return at != null && at.year == ref.year && at.month == ref.month;
    }).length;
  }
}
