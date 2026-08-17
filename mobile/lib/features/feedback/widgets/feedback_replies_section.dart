/// Replies Khaled has written back, shown above the compose form.
///
/// This is the half of the feedback loop that was missing: a parent could
/// report a problem and never hear anything again, which quietly teaches
/// people that reporting is pointless. Now an answer written in Telegram lands
/// here — and, if push is working, arrives as a notification too.
///
/// Fails silent by design. The client returns an empty list on any error, so a
/// broken session shows "no replies yet" rather than an error banner on the
/// screen someone opened *because* something was already broken.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../l10n/app_localizations.dart';
import '../../../models/api_models.dart';
import '../../../state/chat_notifier.dart' show tgClientProvider;
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';

/// Refetched whenever the feedback screen is opened.
final feedbackRepliesProvider =
    FutureProvider.autoDispose<List<FeedbackReply>>((ref) async {
  return ref.read(tgClientProvider).listFeedbackReplies();
});

class FeedbackRepliesSection extends ConsumerWidget {
  const FeedbackRepliesSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final async = ref.watch(feedbackRepliesProvider);

    return async.maybeWhen(
      data: (replies) {
        if (replies.isEmpty) return const SizedBox.shrink();
        // Clear the unread marks once they have actually been rendered.
        WidgetsBinding.instance.addPostFrameCallback((_) {
          final client = ref.read(tgClientProvider);
          for (final r in replies.where((r) => !r.read)) {
            client.markFeedbackReplyRead(r.id);
          }
        });

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              l10n.feedbackRepliesTitle,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 10),
            for (final reply in replies) _ReplyBubble(reply: reply),
            const SizedBox(height: 24),
            const Divider(),
            const SizedBox(height: 16),
          ],
        );
      },
      // Loading and error both render nothing: replies are a bonus on this
      // screen, never a reason to block or alarm.
      orElse: () => const SizedBox.shrink(),
    );
  }
}

class _ReplyBubble extends StatelessWidget {
  const _ReplyBubble({required this.reply});

  final FeedbackReply reply;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Color.lerp(Dt.primary, Dt.surface, .9),
        borderRadius: BorderRadius.circular(Dt.rCard),
        border: Border.all(
          color: reply.read
              ? Colors.transparent
              : Dt.primary.withValues(alpha: .35),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('💬', style: TextStyle(fontSize: 16)),
              const SizedBox(width: 8),
              Text(
                AppLocalizations.of(context).feedbackReplyFrom,
                style: TextStyle(
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                  color: Dt.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            reply.text,
            style: TextStyle(
              fontSize: 14,
              height: 1.6,
              color: AppTheme.textSecondary,
            ),
          ),
        ],
      ),
    );
  }
}
