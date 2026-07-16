/// Daily routine models for «حِساب اليوم».
library;

import 'package:almorabbi/l10n/app_localizations.dart';

enum RoutineEventType { sleep, feed, diaper }

extension RoutineEventTypeX on RoutineEventType {
  String get wireName {
    switch (this) {
      case RoutineEventType.sleep:
        return 'sleep';
      case RoutineEventType.feed:
        return 'feed';
      case RoutineEventType.diaper:
        return 'diaper';
    }
  }

  String label(AppLocalizations l10n) {
    switch (this) {
      case RoutineEventType.sleep:
        return l10n.routineEventSleep;
      case RoutineEventType.feed:
        return l10n.routineEventFeed;
      case RoutineEventType.diaper:
        return l10n.routineEventDiaper;
    }
  }

  String get icon {
    switch (this) {
      case RoutineEventType.sleep:
        return '🌙';
      case RoutineEventType.feed:
        return '🍼';
      case RoutineEventType.diaper:
        return '👶';
    }
  }
}

class RoutineEvent {
  final int? id;
  final int? routineId;
  final RoutineEventType eventType;
  final DateTime startedAt;
  final DateTime? endedAt;
  final String? feedType;
  final int? amountMl;
  final String? side;
  final String? diaperType;
  final String? notes;
  final String source;

  const RoutineEvent({
    this.id,
    this.routineId,
    required this.eventType,
    required this.startedAt,
    this.endedAt,
    this.feedType,
    this.amountMl,
    this.side,
    this.diaperType,
    this.notes,
    this.source = 'manual',
  });

  factory RoutineEvent.fromJson(Map<String, dynamic> json) {
    return RoutineEvent(
      id: json['id'] as int?,
      routineId: json['routine_id'] as int?,
      eventType: RoutineEventType.values.firstWhere(
        (e) => e.wireName == (json['event_type'] as String),
        orElse: () => RoutineEventType.sleep,
      ),
      startedAt: DateTime.parse(json['started_at'] as String),
      endedAt: json['ended_at'] == null
          ? null
          : DateTime.parse(json['ended_at'] as String),
      feedType: json['feed_type'] as String?,
      amountMl: json['amount_ml'] as int?,
      side: json['side'] as String?,
      diaperType: json['diaper_type'] as String?,
      notes: json['notes'] as String?,
      source: (json['source'] as String?) ?? 'manual',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'event_type': eventType.wireName,
      'started_at': startedAt.toUtc().toIso8601String(),
      'ended_at': endedAt?.toUtc().toIso8601String(),
      if (feedType != null) 'feed_type': feedType,
      if (amountMl != null) 'amount_ml': amountMl,
      if (side != null) 'side': side,
      if (diaperType != null) 'diaper_type': diaperType,
      if (notes != null) 'notes': notes,
      'source': source,
    };
  }

  RoutineEvent copyWith({DateTime? endedAt, String? notes, int? amountMl}) {
    return RoutineEvent(
      id: id,
      routineId: routineId,
      eventType: eventType,
      startedAt: startedAt,
      endedAt: endedAt ?? this.endedAt,
      feedType: feedType,
      amountMl: amountMl ?? this.amountMl,
      side: side,
      diaperType: diaperType,
      notes: notes ?? this.notes,
      source: source,
    );
  }
}

class RoutineDay {
  final int routineId;
  final int childId;
  final String routineDate;
  final List<RoutineEvent> events;

  const RoutineDay({
    required this.routineId,
    required this.childId,
    required this.routineDate,
    required this.events,
  });

  factory RoutineDay.fromJson(Map<String, dynamic> json) {
    return RoutineDay(
      routineId: json['routine_id'] as int,
      childId: json['child_id'] as int,
      routineDate: json['routine_date'] as String,
      events: (json['events'] as List?)
              ?.map((e) => RoutineEvent.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class RoutineSummary {
  final int days;
  final int totalSleepMinutes;
  final int totalFeedCount;
  final int totalFeedAmountMl;
  final int diaperCount;

  const RoutineSummary({
    required this.days,
    required this.totalSleepMinutes,
    required this.totalFeedCount,
    required this.totalFeedAmountMl,
    required this.diaperCount,
  });

  factory RoutineSummary.fromJson(Map<String, dynamic> json) {
    return RoutineSummary(
      days: json['days'] as int,
      totalSleepMinutes: json['total_sleep_minutes'] as int,
      totalFeedCount: json['total_feed_count'] as int,
      totalFeedAmountMl: json['total_feed_amount_ml'] as int,
      diaperCount: json['diaper_count'] as int,
    );
  }
}
