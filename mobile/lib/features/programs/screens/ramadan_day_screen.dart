/// Any day of «رمضان العائلة» (`GET /api/children/{id}/ramadan/days/{day}`).
///
/// Two reasons to open a day that is not today: tomorrow's challenge may need
/// paper bought today, and yesterday's «تمّ» may have been forgotten. A past
/// day shows its ticks; a day not yet reached shows its content only. Nothing
/// on this screen ever says a day was missed.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../../../widgets/ui/loading_view.dart';
import '../providers/programs_providers.dart';
import '../widgets/program_widgets.dart';
import '../widgets/ramadan_widgets.dart';

class RamadanDayScreen extends ConsumerWidget {
  const RamadanDayScreen({super.key, required this.childId, required this.day});
  final int childId;
  final int day;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final view = ref.watch(ramadanDayProvider((childId, day)));
    final name =
        programChildProfile(ref, childId)?.name ?? l10n.childFallbackName;
    return Scaffold(
      appBar: AppBar(title: Text(l10n.ramadanDayN(day))),
      body: view.when(
        loading: () => const LoadingView(count: 3),
        error: (e, _) => ProgramErrorView(
          error: e,
          onRetry: () => ref.invalidate(ramadanDayProvider((childId, day))),
        ),
        data: (v) {
          final content = v.content;
          if (content == null) {
            return ProgramNote(emoji: '🌙', text: l10n.programsUnavailable);
          }
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
            children: [
              RamadanDayCard(
                childId: childId,
                childName: name,
                content: content,
                marks: v.marks,
                markable: v.markable,
              ),
              if (!v.markable)
                ProgramSection(
                  child: Text(
                    l10n.ramadanDayPreviewNote,
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(height: 1.5),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
