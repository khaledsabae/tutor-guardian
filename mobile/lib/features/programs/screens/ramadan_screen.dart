/// «رمضان العائلة» for one child (`GET /api/children/{id}/ramadan/today`).
///
/// What the screen shows follows the family's calendar:
///   upcoming  the countdown, how to get ready, each child's fasting step
///   ramadan   today's card (challenge, the child's part, the note, the Quran
///             portion, tonight's story, the family's «تمّ» lanterns), the
///             fasting step, and the street of the month's thirty lanterns
///   eid       the day's activities and the «رمضان عائلتنا» card
///   after     the four bridge weeks and the habits worth keeping
///   off_season a short goodbye, and last season's card if there is one
/// The family challenge and the marks are the family's; the part, the fasting
/// step and the ladder are the child's — the switcher on top changes child.
library;

import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/analytics.dart';
import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../../../widgets/ui/loading_view.dart';
import '../../../widgets/ui/paper_lantern.dart';
import '../data/programs_models.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';
import '../widgets/ramadan_widgets.dart';

class RamadanScreen extends ConsumerStatefulWidget {
  const RamadanScreen({super.key, required this.childId});
  final int childId;

  @override
  ConsumerState<RamadanScreen> createState() => _RamadanScreenState();
}

class _RamadanScreenState extends ConsumerState<RamadanScreen> {
  late int _childId = widget.childId;

  /// Today's marks as the parent just left them — the street lights today's
  /// lantern on the tap, not after the refetch.
  ({int day, RamadanMarks marks})? _live;

  /// The lit days of the street: what the server says the family marked,
  /// with today taken from the marks on screen.
  Set<int> _litDays(RamadanToday t) {
    final lit = {...t.daysMarked};
    final day = t.state == RamadanState.ramadan ? t.day : null;
    if (day == null) return lit;
    final live = _live;
    final marks = live != null && live.day == day ? live.marks : t.marks;
    if (marks != null) {
      if (marks.anyDone) {
        lit.add(day);
      } else {
        lit.remove(day);
      }
    }
    return lit;
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final today = ref.watch(ramadanTodayProvider(_childId));
    final data = today.valueOrNull;
    final season = data?.season;
    final canSet = season != null && data!.state != RamadanState.offSeason;

    return Scaffold(
      appBar: AppBar(
        title: Text(data?.title ?? l10n.programsRamadanTitle),
        actions: [
          if (canSet)
            IconButton(
              tooltip: l10n.ramadanSettingsTitle,
              icon: const Icon(Icons.nightlight_round_outlined),
              onPressed: () => showRamadanSettingsSheet(context, season),
            ),
        ],
      ),
      body: today.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) => ProgramErrorView(
          error: e,
          onRetry: () => ref.invalidate(ramadanTodayProvider(_childId)),
        ),
        data: (t) => RefreshIndicator(
          onRefresh: () => ref.refresh(ramadanTodayProvider(_childId).future),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
            physics: const AlwaysScrollableScrollPhysics(),
            children: [
              _ChildSwitcher(
                selected: _childId,
                onSelected: (id) => setState(() => _childId = id),
              ),
              if (t.subtitle != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: ContentText(
                    t.subtitle!,
                    style: TextStyle(
                      color: context.colors.textSecondary,
                      height: 1.5,
                    ),
                  ),
                ),
              ..._stateBody(context, t),
              if (t.bandsText != null) _WhoSeesWhat(text: t.bandsText!),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _stateBody(BuildContext context, RamadanToday t) {
    final l10n = AppLocalizations.of(context);
    final name =
        programChildProfile(ref, _childId)?.name ?? l10n.childFallbackName;
    final fasting = t.fasting;
    final fastingCard = fasting == null
        ? null
        : FastingSummaryCard(
            childId: _childId,
            childName: name,
            fasting: fasting,
            inMonth: t.state == RamadanState.ramadan,
          );
    switch (t.state) {
      case RamadanState.upcoming:
        return [
          _UpcomingHeader(today: t),
          if (t.kickoff != null) _KickoffCard(kickoff: t.kickoff!),
          ?fastingCard,
          // After 1448's bridge this is the 1449 countdown, and last season's
          // card must stay reachable through it.
          _LastSeasonRecapLink(counting: t.season),
        ];
      case RamadanState.ramadan:
        final content = t.content;
        return [
          if (content != null)
            RamadanDayCard(
              childId: _childId,
              childName: name,
              content: content,
              marks: t.marks,
              markable: t.marks != null,
              onMarksChanged: (m) =>
                  setState(() => _live = (day: content.day, marks: m)),
            ),
          if (t.day == 29) _EidTomorrowCard(season: t.season),
          ?fastingCard,
          if (t.season != null)
            RamadanLanternStreet(
              childId: _childId,
              season: t.season!,
              today: t.day,
              lit: _litDays(t),
            ),
          _RecapLink(soFar: true),
        ];
      case RamadanState.eid:
        return [
          if (t.eid != null) _EidCard(eid: t.eid!, childName: name),
          _RecapLink(soFar: false, prominent: true),
          if (t.season != null)
            RamadanLanternStreet(
              childId: _childId,
              season: t.season!,
              today: null,
              lit: _litDays(t),
            ),
        ];
      case RamadanState.after:
        return [
          if (t.after != null) _AfterCard(after: t.after!, childId: _childId),
          if (t.recapAvailable) _RecapLink(soFar: false),
          if (t.season != null)
            RamadanLanternStreet(
              childId: _childId,
              season: t.season!,
              today: null,
              lit: _litDays(t),
            ),
        ];
      case RamadanState.offSeason:
        return [
          ProgramNote(emoji: '🌙', text: l10n.ramadanOffSeasonBody),
          if (t.recapAvailable) _RecapLink(soFar: false),
        ];
    }
  }
}

/// Chips to move between the family's children (the day's part is per child).
class _ChildSwitcher extends ConsumerWidget {
  const _ChildSwitcher({required this.selected, required this.onSelected});
  final int selected;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ids =
        ref
            .watch(programsOverviewProvider)
            .valueOrNull
            ?.children
            .map((c) => c.childId)
            .toList() ??
        const <int>[];
    if (ids.length < 2) return const SizedBox.shrink();
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          for (final id in ids)
            ChoiceChip(
              label: Text(
                programChildProfile(ref, id)?.name ?? l10n.childFallbackName,
              ),
              selected: id == selected,
              onSelected: (_) => onSelected(id),
            ),
        ],
      ),
    );
  }
}

class _UpcomingHeader extends StatelessWidget {
  const _UpcomingHeader({required this.today});
  final RamadanToday today;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final season = today.season;
    final days = today.daysUntilStart;
    return ProgramSection(
      tone: SectionTone.highlight,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const ExcludeSemantics(
            child: Text('🌙', style: TextStyle(fontSize: 40)),
          ),
          if (days != null)
            Text(
              l10n.ramadanCountdown(days),
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
                color: c.ink,
              ),
            ),
          if (season != null) ...[
            const SizedBox(height: 4),
            Text(
              season.isEstimate
                  ? l10n.ramadanStartsOnEstimate(
                      programDate(context, season.startsOn),
                    )
                  : l10n.ramadanStartsOn(programDate(context, season.startsOn)),
              style: TextStyle(color: c.textSecondary, height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}

class _KickoffCard extends StatelessWidget {
  const _KickoffCard({required this.kickoff});
  final RamadanKickoff kickoff;

  @override
  Widget build(BuildContext context) {
    return ProgramSection(
      title: kickoff.title,
      emoji: '📝',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (kickoff.text != null) ...[
            ContentText(kickoff.text!),
            const SizedBox(height: 10),
          ],
          ProgramBullets(kickoff.setupSteps, numbered: true),
        ],
      ),
    );
  }
}

/// Day 29, from the afternoon: if Eid was announced for tomorrow, the family
/// sets the month to 29 days so the program reaches Eid with them.
class _EidTomorrowCard extends ConsumerWidget {
  const _EidTomorrowCard({required this.season});
  final RamadanSeason? season;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = ref.watch(programsClockProvider)();
    final s = season;
    if (s == null || s.days != 30 || now.hour < 15) {
      return const SizedBox.shrink();
    }
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      title: l10n.ramadanEidTomorrowTitle,
      emoji: '🌙',
      tone: SectionTone.highlight,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            l10n.ramadanEidTomorrowBody,
            style: TextStyle(color: context.colors.ink, height: 1.6),
          ),
          Align(
            alignment: AlignmentDirectional.centerStart,
            child: TextButton(
              onPressed: () => showRamadanSettingsSheet(context, s),
              child: Text(l10n.ramadanSettingsTitle),
            ),
          ),
        ],
      ),
    );
  }
}

/// The month as a street of paper lanterns, strung in rows across it — every
/// day reachable, because tomorrow may need something bought today and
/// yesterday's «تمّ» may have been forgotten.
///
/// A day the family marked anything on is lit; every other day — before
/// today or after it — is the same quiet paper. Nothing is greyed, crossed or
/// counted: there is no missed day on this street (plan, fixed rules), and it
/// is the family's own calendar, never shared or compared. Today's lantern
/// hangs a little larger.
///
/// Each day keeps `ValueKey('ramadan_day_$d')` and says "Day N" (and
/// ", today") to a screen reader, as the chips it replaces did.
class RamadanLanternStreet extends StatelessWidget {
  const RamadanLanternStreet({
    super.key,
    required this.childId,
    required this.season,
    required this.today,
    this.lit = const {},
  });

  final int childId;
  final RamadanSeason season;

  /// The day of the month today, or null outside the month (Eid, after).
  final int? today;

  /// The days the family marked anything on.
  final Set<int> lit;

  /// A day is never narrower than a 48dp tap target.
  static const double minCell = 48;

  /// How many lanterns a string holds at [width]: ten (the month's three
  /// tens) on a wide screen, six on a phone, five on a small one — always a
  /// divisor of thirty so the rows come out even.
  static int columnsFor(double width) {
    for (final cols in const [10, 6, 5]) {
      if (width >= cols * minCell) return cols;
    }
    return math.max(1, (width / minCell).floor());
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return ProgramSection(
      title: l10n.ramadanOtherDays,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            l10n.ramadanStreetHint,
            style: TextStyle(
              color: c.textSecondary,
              fontSize: 12.5,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 6),
          LayoutBuilder(
            builder: (context, box) {
              final cols = columnsFor(box.maxWidth);
              final cell = box.maxWidth / cols;
              return Column(
                children: [
                  for (var first = 1; first <= season.days; first += cols)
                    _LanternString(
                      days: [
                        for (
                          var d = first;
                          d < first + cols && d <= season.days;
                          d++
                        )
                          d,
                      ],
                      cols: cols,
                      cell: cell,
                      row: (first - 1) ~/ cols,
                      today: today,
                      lit: lit,
                      onOpen: (d) {
                        unawaited(Analytics.programAction('ramadan', 'day'));
                        Navigator.of(
                          context,
                        ).push(AppRoutes.ramadanDay(childId, d));
                      },
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

/// One string of lanterns across the street: a rope that sags a little, and
/// each lantern on its own thread at its own length.
class _LanternString extends StatelessWidget {
  const _LanternString({
    required this.days,
    required this.cols,
    required this.cell,
    required this.row,
    required this.today,
    required this.lit,
    required this.onOpen,
  });

  final List<int> days;
  final int cols;
  final double cell;
  final int row;
  final int? today;
  final Set<int> lit;
  final ValueChanged<int> onOpen;

  /// Thread lengths, so the lanterns do not hang in a ruler-straight line.
  static const _threads = [6.0, 13.0, 9.0, 15.0, 7.0, 12.0, 5.0, 14.0, 8.0, 11.0];
  static const double _ropeTop = 3;
  static const double _sag = 7;

  /// The rope's height at a fraction of the street's width.
  static double ropeAt(double t) => _ropeTop + _sag * 4 * t * (1 - t);

  @override
  Widget build(BuildContext context) {
    final c = context.colors;
    final width = cell * cols;
    final drops = [
      for (var i = 0; i < days.length; i++)
        ropeAt((i + .5) / cols) + _threads[(i + row * 3) % _threads.length],
    ];
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Stack(
        children: [
          Positioned.fill(
            child: CustomPaint(
              painter: _RopePainter(
                cols: cols,
                count: days.length,
                drops: drops,
                ropeAt: ropeAt,
                rtl: Directionality.of(context) == TextDirection.rtl,
                color: c.paperEmerald,
              ),
            ),
          ),
          SizedBox(
            width: width,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (var i = 0; i < days.length; i++)
                  _StreetLantern(
                    day: days[i],
                    width: cell,
                    drop: drops[i],
                    isToday: days[i] == today,
                    lit: lit.contains(days[i]),
                    onTap: () => onOpen(days[i]),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _RopePainter extends CustomPainter {
  const _RopePainter({
    required this.cols,
    required this.count,
    required this.drops,
    required this.ropeAt,
    required this.rtl,
    required this.color,
  });

  final int cols;
  final int count;
  final List<double> drops;
  final double Function(double) ropeAt;
  final bool rtl;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final rope = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.6
      ..strokeCap = StrokeCap.round;
    final path = Path()..moveTo(0, ropeAt(0));
    for (var x = 4.0; x <= size.width; x += 4) {
      path.lineTo(x, ropeAt(x / size.width));
    }
    canvas.drawPath(path, rope);
    final thread = Paint()
      ..color = color
      ..strokeWidth = 1.1;
    final cell = size.width / cols;
    for (var i = 0; i < count; i++) {
      final t = (i + .5) / cols;
      final x = rtl ? size.width - (i + .5) * cell : (i + .5) * cell;
      // Down to the lantern's ring (4/48 of the lantern below its top).
      canvas.drawLine(Offset(x, ropeAt(t)), Offset(x, drops[i] + 3), thread);
    }
  }

  @override
  bool shouldRepaint(_RopePainter old) =>
      old.cols != cols ||
      old.count != count ||
      old.rtl != rtl ||
      old.color != color ||
      old.drops.length != drops.length;
}

/// One day on the street: a lantern on its thread and the day's number. A
/// button that opens the day; to a screen reader, "Day N" (", today"), and
/// "lantern lit" when it is — an unlit day says nothing more.
class _StreetLantern extends StatelessWidget {
  const _StreetLantern({
    required this.day,
    required this.width,
    required this.drop,
    required this.isToday,
    required this.lit,
    required this.onTap,
  });

  final int day;
  final double width;
  final double drop;
  final bool isToday;
  final bool lit;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    return Semantics(
      key: ValueKey('ramadan_day_$day'),
      container: true,
      button: true,
      label: isToday ? l10n.ramadanDayToday(day) : l10n.ramadanDayN(day),
      value: lit ? l10n.ramadanLanternLit : null,
      onTap: onTap,
      excludeSemantics: true,
      child: SizedBox(
        width: width,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: EdgeInsets.only(top: drop, bottom: 4),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                PaperLantern(lit: lit, height: isToday ? 50 : 40),
                const SizedBox(height: 2),
                Text(
                  '$day',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: isToday ? c.primary : c.ink,
                    fontWeight: isToday ? FontWeight.w800 : FontWeight.w600,
                    fontSize: 12.5,
                    height: 1.2,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Last season's «رمضان عائلتنا», during the next season's countdown. Shown
/// only when the server has a card for an earlier season than the one counted
/// down to — before the very first season there is nothing to open.
class _LastSeasonRecapLink extends ConsumerWidget {
  const _LastSeasonRecapLink({required this.counting});
  final RamadanSeason? counting;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final recap = ref.watch(ramadanRecapProvider).valueOrNull;
    final year = recap?.hijriYear;
    final ahead = counting?.hijriYear;
    if (recap?.card == null ||
        year == null ||
        (ahead != null && year >= ahead)) {
      return const SizedBox.shrink();
    }
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      child: ProgramLinkRow(
        key: const ValueKey('ramadan_last_recap'),
        emoji: '🤍',
        label: l10n.ramadanRecapLastSeason,
        onTap: () {
          unawaited(Analytics.programAction('ramadan', 'recap'));
          Navigator.of(context).push(AppRoutes.ramadanRecap());
        },
      ),
    );
  }
}

class _RecapLink extends StatelessWidget {
  const _RecapLink({required this.soFar, this.prominent = false});
  final bool soFar;
  final bool prominent;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      tone: prominent ? SectionTone.highlight : SectionTone.plain,
      child: ProgramLinkRow(
        emoji: '🤍',
        label: soFar ? l10n.ramadanSoFar : l10n.ramadanRecapOpen,
        onTap: () {
          unawaited(Analytics.programAction('ramadan', 'recap'));
          Navigator.of(context).push(AppRoutes.ramadanRecap());
        },
      ),
    );
  }
}

class _EidCard extends StatelessWidget {
  const _EidCard({required this.eid, required this.childName});
  final RamadanEid eid;
  final String childName;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ProgramSection(
          title: eid.title,
          emoji: '🎉',
          tone: SectionTone.highlight,
          child: ProgramBullets(eid.activities),
        ),
        if (eid.variant != null)
          ProgramSection(
            title: l10n.ramadanChildPart(childName),
            emoji: '🧒',
            child: ContentText(eid.variant!.text),
          ),
        if (eid.parentNote != null)
          ProgramSection(
            title: l10n.ramadanParentNote,
            emoji: '💬',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ContentText(eid.parentNote!.text),
                EvidenceCards(eid.parentNote!.evidence),
              ],
            ),
          ),
        if (!eid.quran.isEmpty)
          ProgramSection(
            title: l10n.ramadanWirdTitle,
            emoji: '📗',
            child: RamadanQuranBlock(quran: eid.quran),
          ),
        if (eid.evidence.isNotEmpty && eid.parentNote == null)
          ProgramSection(
            title: l10n.programsEvidenceTitle,
            child: EvidenceCards(eid.evidence),
          ),
      ],
    );
  }
}

class _AfterCard extends StatelessWidget {
  const _AfterCard({required this.after, required this.childId});
  final RamadanAfter after;
  final int childId;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final c = context.colors;
    final week = after.week;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ProgramSection(
          title: after.title,
          emoji: '🌱',
          tone: SectionTone.highlight,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (after.text != null) ContentText(after.text!),
              EvidenceCards(after.evidence),
            ],
          ),
        ),
        if (week != null)
          ProgramSection(
            title: l10n.ramadanAfterThisWeek,
            emoji: '📌',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ContentText(
                  week.title,
                  style: TextStyle(
                    color: c.ink,
                    fontWeight: FontWeight.w800,
                    height: 1.5,
                  ),
                ),
                if (week.text != null) ...[
                  const SizedBox(height: 4),
                  ContentText(week.text!),
                ],
              ],
            ),
          ),
        if (after.keepHabits.isNotEmpty)
          ProgramSection(
            title: l10n.ramadanAfterHabits,
            emoji: '🔁',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final h in after.keepHabits)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ContentText(
                          h.title,
                          style: TextStyle(
                            color: c.ink,
                            fontWeight: FontWeight.w700,
                            height: 1.5,
                          ),
                        ),
                        if (h.text != null) ContentText(h.text!),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        if (after.weeks.length > 1)
          ProgramSection(
            title: l10n.ramadanAfterWeeks,
            emoji: '🗓️',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (final w in after.weeks)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ContentText(
                          w.title,
                          style: TextStyle(
                            color: c.ink,
                            fontWeight: FontWeight.w700,
                            height: 1.5,
                          ),
                        ),
                        if (w.text != null) ContentText(w.text!),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        if (!after.links.isEmpty)
          ProgramSection(
            title: l10n.ramadanAfterLinks,
            emoji: '➡️',
            child: ProgramLinksList(links: after.links, childId: childId),
          ),
      ],
    );
  }
}

class _WhoSeesWhat extends StatelessWidget {
  const _WhoSeesWhat({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return ProgramSection(
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: EdgeInsets.zero,
          childrenPadding: const EdgeInsets.only(bottom: 8),
          title: Text(
            l10n.ramadanWhoSeesWhat,
            style: TextStyle(
              color: context.colors.ink,
              fontWeight: FontWeight.w700,
            ),
          ),
          children: [ContentText(text)],
        ),
      ),
    );
  }
}
