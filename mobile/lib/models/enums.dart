/// Stable enums hard-coded from `backend/app/core/taxonomy.py` and
/// `MOBILE_API.md`. These wire values are part of the v1 contract; client
/// never localizes them — UI may map them to display labels separately.
library;

/// Age bands accepted by `/api/assistant/*`.
enum AgeGroup {
  prenatalOne('prenatal-1'),
  twoThree('2-3'),
  fourSix('4-6'),
  sevenNine('7-9'),
  tenTwelve('10-12'),
  thirteenFifteen('13-15'),
  sixteenEighteen('16-18'),
  unspecified('unspecified');

  /// The exact Arabic-free string sent over the wire.
  final String wire;
  const AgeGroup(this.wire);

  /// Human label for the dropdown (Arabic UI).
  String get label {
    switch (this) {
      case AgeGroup.prenatalOne: return 'فترة الحمل وحتى عام';
      case AgeGroup.twoThree: return '2–3 سنوات';
      case AgeGroup.fourSix: return '4–6 سنوات';
      case AgeGroup.sevenNine: return '7–9 سنوات';
      case AgeGroup.tenTwelve: return '10–12 سنة';
      case AgeGroup.thirteenFifteen: return '13–15 سنة';
      case AgeGroup.sixteenEighteen: return '16–18 سنة';
      case AgeGroup.unspecified: return 'غير محدد';
    }
  }

  static AgeGroup fromWire(String? s) {
    if (s == null) return AgeGroup.unspecified;
    // "0-3" is the legacy alias for the prenatal-to-one-year band; show it
    // as «فترة الحمل وحتى عام» everywhere instead of the raw "0-3".
    if (s == '0-3') return AgeGroup.prenatalOne;
    for (final g in AgeGroup.values) {
      if (g.wire == s) return g;
    }
    return AgeGroup.unspecified;
  }

  static const AgeGroup defaultValue = AgeGroup.fourSix;
}

/// Severity levels — Arabic strings on the wire, never translate.
enum Severity {
  light('خفيف'),
  moderate('متوسط'),
  severe('شديد'),
  emergency('طارئ');

  final String wire;
  const Severity(this.wire);

  String get label => switch (this) {
    Severity.light => 'خفيف',
    Severity.moderate => 'متوسط',
    Severity.severe => 'شديد',
    Severity.emergency => 'طارئ',
  };

  static Severity fromWire(String? s) {
    if (s == null) return Severity.moderate;
    for (final v in Severity.values) {
      if (v.wire == s) return v;
    }
    return Severity.moderate;
  }

  static const Severity defaultValue = Severity.moderate;
}

/// Domains returned by the server (canonical, post-alias resolution).
enum Domain {
  medical('medical', 'الصحة والنمو'),
  cyber('cyber', 'الأمان الرقمي'),
  islamicParenting('islamic_parenting', 'التربية الإسلامية'),
  development('development', 'تطور الطفل'),
  unknown('', 'غير محدد');

  final String wire;
  final String labelAr;
  const Domain(this.wire, this.labelAr);

  static Domain fromWire(String? s) {
    if (s == null) return Domain.unknown;
    for (final v in Domain.values) {
      if (v.wire == s) return v;
    }
    return Domain.unknown;
  }
}

/// Response mode (returned in `AssistantReply.mode`).
enum ReplyMode {
  retrievalOnly('retrieval_only', 'بحث فقط'),
  llmGenerated('llm_generated', 'ذكاء اصطناعي'),
  banned('banned', 'خارج النطاق'),
  emergency('emergency', 'حالة طارئة'),
  unknown('', 'غير محدد');

  final String wire;
  final String labelAr;
  const ReplyMode(this.wire, this.labelAr);

  static ReplyMode fromWire(String? s) {
    if (s == null) return ReplyMode.unknown;
    for (final v in ReplyMode.values) {
      if (v.wire == s) return v;
    }
    return ReplyMode.unknown;
  }
}

/// Where the parent should be directed to.
enum EscalationTarget {
  pediatrician('pediatrician', 'طبيب أطفال'),
  cybersecuritySpecialist('cybersecurity_specialist', 'متخصص بالأمان الرقمي'),
  emergencyServices('emergency_services', 'خدمات الطوارئ'),
  none(null, '');

  final String? wire;
  final String labelAr;
  const EscalationTarget(this.wire, this.labelAr);

  static EscalationTarget fromWire(Object? s) {
    if (s == null) return EscalationTarget.none;
    final str = s.toString();
    for (final v in EscalationTarget.values) {
      if (v.wire == str) return v;
    }
    return EscalationTarget.none;
  }
}
