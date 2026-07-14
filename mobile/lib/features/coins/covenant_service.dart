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

  static const _kCovenants = 'covenant.list';

  final List<Covenant> _defaults = const [
    Covenant(id: 'def_1', title: 'شراء مثلجات لذيذة 🍦', cost: 30),
    Covenant(id: 'def_2', title: 'نصف ساعة لعب إضافية 🎮', cost: 50),
    Covenant(id: 'def_3', title: 'رحلة عائلية مميزة للحديقة 🌳', cost: 100),
  ];

  Future<List<Covenant>> load() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_kCovenants);
    if (raw == null) {
      // Save and return defaults first time
      await save(_defaults);
      return _defaults;
    }
    try {
      final list = jsonDecode(raw) as List;
      return list.map((e) => Covenant.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      return _defaults;
    }
  }

  Future<void> save(List<Covenant> list) async {
    final p = await SharedPreferences.getInstance();
    final raw = jsonEncode(list.map((e) => e.toJson()).toList());
    await p.setString(_kCovenants, raw);
  }

  Future<void> add(String title, int cost) async {
    final list = await load();
    final newItem = Covenant(
      id: 'cov_${DateTime.now().millisecondsSinceEpoch}',
      title: title,
      cost: cost,
    );
    list.add(newItem);
    await save(list);
  }

  Future<bool> redeem(String id) async {
    final list = await load();
    final idx = list.indexWhere((e) => e.id == id);
    if (idx == -1) return false;
    list[idx] = list[idx].copyWith(
      isRedeemed: true,
      redeemedAt: DateTime.now().toIso8601String(),
    );
    await save(list);
    return true;
  }

  Future<void> deliver(String id) async {
    final list = await load();
    final idx = list.indexWhere((e) => e.id == id);
    if (idx == -1) return;
    list[idx] = list[idx].copyWith(isDelivered: true);
    await save(list);
  }

  Future<void> delete(String id) async {
    final list = await load();
    list.removeWhere((e) => e.id == id);
    await save(list);
  }
}
