/// The quiet moment when the parent moves the Prayer Journey up a stage
/// (NOOR_WAL_QANADIL_PLAN, phase 4): «انتقل أحمد إلى «الوضوء». أعانكم الله
/// وتقبّل منكم» — a sheet of paper with Noor, calm. No confetti, no sound, no
/// count: worship is in no counter (the plan's decision), so the stage is
/// named by its title, never by its number. Moving back never shows it; the
/// screen decides that.
library;

import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../companion/widgets/noor_face.dart';
import '../../companion/widgets/noor_presence.dart';

// The paper (assets/svg/STYLE.md): ivory on a light page, the deep road
// paper on a dark one.
const _kPaper = Color(0xFFFBF1DE);
const _kPaperEdge = Color(0xFFD9C7A7);
const _kPaperDark = Color(0xFF1F4A43);
const _kInk = Color(0xFF0F3D36);
const _kEmerald = Color(0xFF0D6A5A);
const _kLeaf = Color(0xFFA8E6C4);

/// Shows the moment. [line] is the move itself, already worded for the
/// child (or the family, when the child has no name of its own).
Future<void> showPrayerStageMoment(BuildContext context, {required String line}) =>
    showDialog<void>(
      context: context,
      builder: (_) => PrayerStageMoment(line: line),
    );

class PrayerStageMoment extends StatelessWidget {
  const PrayerStageMoment({super.key, required this.line});

  final String line;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final ink = dark ? _kPaper : _kInk;
    return Dialog(
      key: const ValueKey('prayer_stage_moment'),
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
      shadowColor: Colors.transparent,
      elevation: 0,
      insetPadding: const EdgeInsets.symmetric(horizontal: 28, vertical: 32),
      child: Container(
        decoration: BoxDecoration(
          color: dark ? _kPaperDark : _kPaper,
          borderRadius: BorderRadius.circular(28),
          border: dark ? null : Border.all(color: _kPaperEdge, width: 1.5),
          // A cut-paper drop: flat, offset, no blur.
          boxShadow: const [
            BoxShadow(color: Color(0x330F3D36), offset: Offset(4, 5)),
          ],
        ),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(22, 22, 22, 10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const NoorPresence(size: 72, face: NoorFaceState.calm),
              const SizedBox(height: 14),
              Text(
                line,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: ink,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                l10n.prayerStageMomentDua,
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: dark ? _kLeaf : _kEmerald,
                  fontSize: 15,
                  height: 1.6,
                ),
              ),
              const SizedBox(height: 10),
              TextButton(
                key: const ValueKey('prayer_stage_moment_close'),
                style: TextButton.styleFrom(
                  foregroundColor: ink,
                  minimumSize: const Size(0, 48),
                ),
                onPressed: () => Navigator.of(context).pop(),
                child: Text(l10n.close),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
