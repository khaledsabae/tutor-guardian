/// The optional birth month on a child's profile (MOBILE_API §11.1).
///
/// A month, never a day: it is enough to time the milestone reminders and the
/// Prayer Journey ("turning seven next month"), and it is the least a parent
/// has to hand over. The field says why it is asked for, can be removed at any
/// time, and is offered only when the server can store it (see the add/edit
/// screens).
library;

import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../../models/enums.dart';
import '../../../theme/app_colors.dart';
import 'program_widgets.dart';

/// `(year, month)` from "YYYY-MM", or null.
(int, int)? parseBirthMonth(String? value) {
  final m = RegExp(
    r'^(\d{4})-(0[1-9]|1[0-2])$',
  ).firstMatch(value?.trim() ?? '');
  if (m == null) return null;
  return (int.parse(m.group(1)!), int.parse(m.group(2)!));
}

String formatBirthMonth(int year, int month) =>
    '$year-${month.toString().padLeft(2, '0')}';

/// The age band a birth month puts a child in on [today] — the same rule as
/// the server's `band_for_age_months`, so the hint never disagrees with what
/// the programs will use.
String? bandForBirthMonth(String? birthMonth, DateTime today) {
  final parsed = parseBirthMonth(birthMonth);
  if (parsed == null) return null;
  final months = (today.year - parsed.$1) * 12 + (today.month - parsed.$2);
  if (months < 12) return 'prenatal-1';
  final years = months ~/ 12;
  for (final (upper, band) in const [
    (4, '2-3'),
    (7, '4-6'),
    (10, '7-9'),
    (13, '10-12'),
    (16, '13-15'),
  ]) {
    if (years < upper) return band;
  }
  return '16-18';
}

/// The month range the server accepts: ten months ahead (an expected baby)
/// to nineteen years back.
(DateTime, DateTime) birthMonthRange(DateTime today) => (
  DateTime(today.year - 19, today.month),
  DateTime(today.year, today.month + 10),
);

class BirthMonthField extends StatelessWidget {
  const BirthMonthField({
    super.key,
    required this.value,
    required this.onChanged,
    this.childName,
    this.ageGroup,
    this.onUseBand,
    this.today,
  });

  /// "YYYY-MM" or null.
  final String? value;
  final ValueChanged<String?> onChanged;
  final String? childName;

  /// The age group currently chosen on the form.
  final String? ageGroup;

  /// Offered when the month and the chosen age group disagree.
  final ValueChanged<String>? onUseBand;

  /// For tests; defaults to now.
  final DateTime? today;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final parsed = parseBirthMonth(value);
    final now = today ?? DateTime.now();
    final band = bandForBirthMonth(value, now);
    final mismatch =
        band != null &&
        ageGroup != null &&
        band != ageGroup &&
        onUseBand != null;
    final name = (childName == null || childName!.trim().isEmpty)
        ? l10n.childFallbackName
        : childName!.trim();

    return Column(
      key: const ValueKey('birth_month_field'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          l10n.birthMonthLabel,
          style: Theme.of(
            context,
          ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700),
        ),
        const SizedBox(height: 4),
        Text(
          l10n.birthMonthWhy,
          style: TextStyle(
            color: c.textSecondary,
            fontSize: 12.5,
            height: 1.55,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(
            color: c.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: c.track),
          ),
          child: Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 8,
            children: [
              const ExcludeSemantics(
                child: Text('🎂', style: TextStyle(fontSize: 20)),
              ),
              Text(
                parsed == null
                    ? l10n.birthMonthNotSet
                    : programMonthYear(context, parsed.$1, parsed.$2),
                style: TextStyle(
                  color: parsed == null ? c.inkSoft : c.ink,
                  fontWeight: parsed == null
                      ? FontWeight.w500
                      : FontWeight.w700,
                ),
              ),
              TextButton(
                key: const ValueKey('birth_month_choose'),
                onPressed: () async {
                  final picked = await showBirthMonthPicker(
                    context,
                    initial: value,
                    today: now,
                  );
                  if (picked != null) onChanged(picked);
                },
                child: Text(
                  parsed == null
                      ? l10n.birthMonthChoose
                      : l10n.birthMonthChange,
                ),
              ),
              if (parsed != null)
                TextButton(
                  key: const ValueKey('birth_month_clear'),
                  onPressed: () => onChanged(null),
                  child: Text(l10n.birthMonthClear),
                ),
            ],
          ),
        ),
        if (mismatch) ...[
          const SizedBox(height: 6),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 4,
            children: [
              Text(
                l10n.birthMonthBandHint(
                  name,
                  AgeGroup.fromWire(band).label(l10n),
                ),
                style: TextStyle(color: c.ink, fontSize: 13, height: 1.5),
              ),
              TextButton(
                key: const ValueKey('birth_month_use_band'),
                onPressed: () => onUseBand!(band),
                child: Text(l10n.birthMonthUseBand),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

/// A year and a month — nothing finer. Returns "YYYY-MM" or null (cancelled).
Future<String?> showBirthMonthPicker(
  BuildContext context, {
  String? initial,
  DateTime? today,
}) {
  final now = today ?? DateTime.now();
  final (earliest, latest) = birthMonthRange(now);
  final start = parseBirthMonth(initial);
  return showDialog<String>(
    context: context,
    builder: (ctx) {
      var year = start?.$1 ?? (now.year - 5);
      int? month = start?.$2;
      return StatefulBuilder(
        builder: (ctx, setState) {
          final l10n = AppLocalizations.of(ctx);
          bool allowed(int m) {
            final d = DateTime(year, m);
            return !d.isBefore(earliest) && !d.isAfter(latest);
          }

          return AlertDialog(
            title: Text(l10n.birthMonthPickerTitle),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  DropdownButtonFormField<int>(
                    key: const ValueKey('birth_month_year'),
                    initialValue: year,
                    isExpanded: true,
                    decoration: InputDecoration(labelText: l10n.birthMonthYear),
                    items: [
                      for (var y = latest.year; y >= earliest.year; y--)
                        DropdownMenuItem(value: y, child: Text('$y')),
                    ],
                    onChanged: (y) => setState(() {
                      year = y ?? year;
                      if (month != null && !allowed(month!)) month = null;
                    }),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: [
                      for (var m = 1; m <= 12; m++)
                        ChoiceChip(
                          key: ValueKey('birth_month_m$m'),
                          label: Text(programMonthName(ctx, m)),
                          selected: month == m,
                          onSelected: allowed(m)
                              ? (_) => setState(() => month = m)
                              : null,
                        ),
                    ],
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: Text(l10n.cancel),
              ),
              FilledButton(
                key: const ValueKey('birth_month_save'),
                onPressed: month == null
                    ? null
                    : () =>
                          Navigator.of(ctx).pop(formatBirthMonth(year, month!)),
                child: Text(l10n.save),
              ),
            ],
          );
        },
      );
    },
  );
}
