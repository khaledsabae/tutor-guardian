/// «مخصّص لأحمد» under an answer that used child memory (MOBILE_API §9.1).
///
/// Tapping it opens «ما يعرفه المربّي عن أحمد»: the parent sees — and can
/// correct — exactly what shaped the answer. Built only when the reply says
/// `memory_facts_used > 0`, so answers from older servers never show it.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/app_routes.dart';
import '../../../l10n/app_localizations.dart';
import '../../../theme/app_colors.dart';
import '../providers/memory_providers.dart';

class PersonalisedChip extends ConsumerWidget {
  const PersonalisedChip({super.key, required this.childId});

  /// The child the server resolved the question to (`metadata.child_id`).
  final int? childId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final colors = context.colors;
    final id = childId;
    final name = id == null ? null : ref.watch(childNameProvider(id));
    final label = name == null ? l10n.memoryChipGeneric : l10n.memoryChipFor(name);
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Semantics(
        button: id != null,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: id == null
              ? null
              : () => Navigator.of(context).push(AppRoutes.childMemory(
                    childId: id,
                    childName: name ?? l10n.memoryYourChild,
                  )),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: colors.primary.withValues(alpha: colors.isDark ? .2 : .08),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.auto_awesome_outlined,
                    size: 14, color: colors.primary),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    label,
                    style: TextStyle(
                      fontSize: 11.5,
                      color: colors.primary,
                      fontWeight: FontWeight.w700,
                    ),
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
