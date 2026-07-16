/// Stable enums hard-coded from `backend/app/core/taxonomy.py` and
/// `MOBILE_API.md`. These wire values are part of the v1 contract; client
/// never localizes them — UI may map them to display labels separately.
library;

import 'package:almorabbi/l10n/app_localizations.dart';

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

  /// Human label for the dropdown.
  String label(AppLocalizations l10n) {
    switch (this) {
      case AgeGroup.prenatalOne: return l10n.ageGroupPrenatal;
      case AgeGroup.twoThree: return l10n.ageGroup2to3;
      case AgeGroup.fourSix: return l10n.ageGroup4to6;
      case AgeGroup.sevenNine: return l10n.ageGroup7to9;
      case AgeGroup.tenTwelve: return l10n.ageGroup10to12;
      case AgeGroup.thirteenFifteen: return l10n.ageGroup13to15;
      case AgeGroup.sixteenEighteen: return l10n.ageGroup16to18;
      case AgeGroup.unspecified: return l10n.unspecified;
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

  String label(AppLocalizations l10n) => switch (this) {
    Severity.light => l10n.severityLight,
    Severity.moderate => l10n.severityModerate,
    Severity.severe => l10n.severitySevere,
    Severity.emergency => l10n.severityEmergency,
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
  medical('medical'),
  cyber('cyber'),
  islamicParenting('islamic_parenting'),
  aqeedah('aqeedah'),
  development('development'),
  unknown('');

  final String wire;
  const Domain(this.wire);

  String label(AppLocalizations l10n) => switch (this) {
    Domain.medical => l10n.domainMedical,
    Domain.cyber => l10n.domainCyber,
    Domain.islamicParenting => l10n.domainIslamicParenting,
    Domain.aqeedah => l10n.domainAqeedah,
    Domain.development => l10n.domainDevelopment,
    Domain.unknown => l10n.unspecified,
  };

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
  retrievalOnly('retrieval_only'),
  llmGenerated('llm_generated'),
  banned('banned'),
  emergency('emergency'),
  unknown('');

  final String wire;
  const ReplyMode(this.wire);

  String label(AppLocalizations l10n) => switch (this) {
    ReplyMode.retrievalOnly => l10n.replyModeRetrieval,
    ReplyMode.llmGenerated => l10n.replyModeAi,
    ReplyMode.banned => l10n.replyModeBanned,
    ReplyMode.emergency => l10n.replyModeEmergency,
    ReplyMode.unknown => l10n.unspecified,
  };

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
  pediatrician('pediatrician'),
  cybersecuritySpecialist('cybersecurity_specialist'),
  emergencyServices('emergency_services'),
  none(null);

  final String? wire;
  const EscalationTarget(this.wire);

  String label(AppLocalizations l10n) => switch (this) {
    EscalationTarget.pediatrician => l10n.escalationPediatrician,
    EscalationTarget.cybersecuritySpecialist => l10n.escalationCyberSpecialist,
    EscalationTarget.emergencyServices => l10n.escalationEmergencyServices,
    EscalationTarget.none => '',
  };

  static EscalationTarget fromWire(Object? s) {
    if (s == null) return EscalationTarget.none;
    final str = s.toString();
    for (final v in EscalationTarget.values) {
      if (v.wire == str) return v;
    }
    return EscalationTarget.none;
  }
}
