/// Phase 8-C — small "note exists" badge for the lesson tile in
/// [PathDetailScreen]. Renders nothing when the user has no
/// reflection on the lesson.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/app_theme.dart';
import '../providers/reflections_providers.dart';

class ReflectionNoteBadge extends ConsumerWidget {
  const ReflectionNoteBadge({super.key, required this.lessonId});
  final String lessonId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final entry = ref.watch(lessonReflectionProvider(lessonId));
    if (entry == null || entry.text.isEmpty) {
      return const SizedBox.shrink();
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: const Color(0xFFFFE9C7),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: const [
          Icon(Icons.edit_note,
              size: 12, color: Color(0xFF8A5A0F)),
          SizedBox(width: 2),
          Text(
            'ملاحظة',
            style: TextStyle(
              color: Color(0xFF8A5A0F),
              fontSize: 10,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}
