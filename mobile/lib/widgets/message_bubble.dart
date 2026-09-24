/// One chat bubble. User bubbles are a teal gradient (right in RTL);
/// assistant bubbles are white cards with a leading avatar (left in
/// RTL). Assistant messages render their content as Markdown (light
/// subset) and show streaming/typing states.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

// Domain enum is used implicitly via the .labelAr getters on AssistantReply
// — keep the import live.
import '../models/api_models.dart';
import '../state/chat_notifier.dart';
import '../theme/app_theme.dart';
import '../theme/design_tokens.dart';
import 'safety_banner.dart';
import '../l10n/app_localizations.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessageUI message;
  final bool isFirstInGroup;
  final bool isLastInGroup;
  final ValueChanged<String>? onFeedback;

  /// Shown on the inline error of this message (the one error surface for a
  /// failed turn — the screen no longer repeats it in a top banner).
  final VoidCallback? onRetry;

  /// Follow-up questions to offer under this (finished) answer; tapping one
  /// sends it. Only the chat's last answer gets them.
  final List<String> followUps;
  final ValueChanged<String>? onFollowUp;

  const MessageBubble({
    super.key,
    required this.message,
    this.isFirstInGroup = true,
    this.isLastInGroup = true,
    this.onFeedback,
    this.onRetry,
    this.followUps = const [],
    this.onFollowUp,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final align =
        isUser ? AlignmentDirectional.centerEnd : AlignmentDirectional.centerStart;

    final radius = BorderRadiusDirectional.only(
      topStart: const Radius.circular(20),
      topEnd: const Radius.circular(20),
      bottomStart: Radius.circular(isUser || isLastInGroup ? 20 : 6),
      bottomEnd: Radius.circular(!isUser || isLastInGroup ? 20 : 6),
    );

    final bubble = Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.78,
      ),
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        gradient: isUser ? Dt.primaryGradient : null,
        color: isUser ? null : Dt.surface,
        borderRadius: radius,
        boxShadow: isUser
            ? Dt.softShadow(Dt.primary, alpha: .18)
            : Dt.cardShadow,
      ),
      child: isUser
          ? Text(
              message.content,
              style: const TextStyle(
                  color: Colors.white, fontSize: 15, height: 1.5),
            )
          : _AssistantBody(
              message: message,
              onFeedback: onFeedback,
            ),
    );

    // Assistant rows get a leading avatar (only on the first bubble of
    // a group); subsequent bubbles keep the indent so text aligns.
    final body = isUser
        ? Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: bubble,
          )
        : Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (isFirstInGroup)
                  Container(
                    width: 34,
                    height: 34,
                    margin: const EdgeInsetsDirectional.only(
                        end: 8, top: 4),
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: .12),
                      shape: BoxShape.circle,
                    ),
                    child: const Text('🧑‍🏫',
                        style: TextStyle(fontSize: 18)),
                  )
                else
                  const SizedBox(width: 42),
                Flexible(child: bubble),
              ],
            ),
          );

    return Align(
      alignment: align,
      child: Column(
        crossAxisAlignment:
            isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          body,
          if (message.error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.error_outline,
                      size: 14, color: AppTheme.dangerFg),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      message.error!,
                      style: TextStyle(
                        fontSize: 12,
                        color: AppTheme.dangerFg,
                      ),
                    ),
                  ),
                  if (onRetry != null)
                    TextButton.icon(
                      onPressed: onRetry,
                      icon: const Icon(Icons.refresh, size: 16),
                      label: Text(AppLocalizations.of(context).chatRetry),
                      style: TextButton.styleFrom(
                          foregroundColor: AppTheme.dangerFg),
                    ),
                ],
              ),
            ),
          if (!isUser &&
              followUps.isNotEmpty &&
              onFollowUp != null &&
              !message.isStreaming &&
              message.error == null)
            _FollowUps(questions: followUps, onTap: onFollowUp!),
        ],
      ),
    );
  }
}

class _AssistantBody extends StatelessWidget {
  final ChatMessageUI message;
  final ValueChanged<String>? onFeedback;
  const _AssistantBody({required this.message, this.onFeedback});

  @override
  Widget build(BuildContext context) {
    final r = message.reply;
    // While nothing has arrived yet the typing dots below are the whole
    // signal; a Markdown "…" above them said the same thing twice.
    final showContent = message.content.isNotEmpty;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (r != null) SafetyBanner(reply: r),
        if (showContent)
          MarkdownBody(
            data: message.content,
            styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context))
                .copyWith(
              // 16/1.7 for long Arabic guidance: diacritics need the leading
              // (UX_UI_ROADMAP §1.3 type ramp).
              p: TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 16,
                height: 1.7,
              ),
              code: TextStyle(
                fontFamily: 'monospace',
                backgroundColor: AppTheme.surfaceAlt,
              ),
            ),
          )
        else
          const SizedBox.shrink(),
        if (message.isStreaming)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            // Before the first token: dots, then reassurance copy if the
            // wait runs long. Once text flows, the text is the signal.
            child: showContent
                ? const _TypingIndicator()
                : const _ThinkingIndicator(),
          ),
        if (r != null && !message.isStreaming) ...[
          const SizedBox(height: 6),
          _MetadataChips(reply: r),
          const SizedBox(height: 4),
          _FeedbackRow(
            current: message.feedback,
            onFeedback: (rating) => onFeedback?.call(rating),
          ),
        ],
      ],
    );
  }
}

/// "Thinking" state of the response lifecycle (UX_UI_ROADMAP §2.2): the
/// typing dots, plus one line of reassurance once the first token is more
/// than [_slowAfter] away — retrieval and a cold model can take that long,
/// and silent dots past that point read as "stuck".
class _ThinkingIndicator extends StatefulWidget {
  const _ThinkingIndicator();

  static const Duration _slowAfter = Duration(seconds: 3);

  @override
  State<_ThinkingIndicator> createState() => _ThinkingIndicatorState();
}

class _ThinkingIndicatorState extends State<_ThinkingIndicator> {
  Timer? _timer;
  bool _slow = false;

  @override
  void initState() {
    super.initState();
    _timer = Timer(_ThinkingIndicator._slowAfter, () {
      if (mounted) setState(() => _slow = true);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      label: _slow ? AppLocalizations.of(context).chatThinkingSlow : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          const _TypingIndicator(),
          AnimatedSize(
            duration: Dt.fast,
            child: _slow
                ? Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      AppLocalizations.of(context).chatThinkingSlow,
                      style: TextStyle(
                          fontSize: 13, color: AppTheme.textMuted),
                    ),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }
}

/// Suggested follow-up questions under the latest answer (UX_UI_ROADMAP §2.3).
class _FollowUps extends StatelessWidget {
  const _FollowUps({required this.questions, required this.onTap});

  final List<String> questions;
  final ValueChanged<String> onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      // Indented to line up with the bubble text, past the avatar column.
      padding: const EdgeInsetsDirectional.only(start: 54, end: 12, top: 4),
      child: Semantics(
        label: AppLocalizations.of(context).chatFollowUpsLabel,
        container: true,
        child: Wrap(
          spacing: Dt.s8,
          runSpacing: Dt.s8,
          children: [
            for (final q in questions)
              ActionChip(
                label: Text(q),
                labelStyle: TextStyle(
                  color: AppTheme.primary,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
                backgroundColor: AppTheme.primary.withValues(alpha: .08),
                side: BorderSide(color: AppTheme.primary.withValues(alpha: .3)),
                shape: const StadiumBorder(),
                onPressed: () => onTap(q),
              ),
          ],
        ),
      ),
    );
  }
}

class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final t = ((_ctrl.value + i * 0.25) % 1.0);
            final opacity = (t < 0.5 ? t * 2 : (1 - t) * 2).clamp(0.2, 1.0);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2),
              child: Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: AppTheme.textMuted.withValues(alpha: opacity),
                  shape: BoxShape.circle,
                ),
              ),
            );
          }),
        );
      },
    );
  }
}

class _MetadataChips extends StatelessWidget {
  final AssistantReply reply;
  const _MetadataChips({required this.reply});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    // `mode` (retrieval_only / llm_generated) is pipeline jargon, not
    // something a parent can act on — dropped from the visible chips.
    final chips = <String>[
      reply.domain.label(l10n),
      reply.severity.label(l10n),
    ];
    return Wrap(
      spacing: 6,
      runSpacing: 4,
      children: chips
          .where((c) => c.isNotEmpty)
          .map(
            (c) => Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                border: Border.all(color: AppTheme.surfaceAlt),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                c,
                style: TextStyle(
                  fontSize: 11,
                  color: AppTheme.textSecondary,
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _FeedbackRow extends StatelessWidget {
  final String? current;
  final ValueChanged<String> onFeedback;
  const _FeedbackRow({required this.current, required this.onFeedback});

  @override
  Widget build(BuildContext context) {
    if (current != null) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            current == 'up' ? Icons.thumb_up : Icons.thumb_down,
            size: 14,
            color: AppTheme.success,
          ),
          const SizedBox(width: 4),
          Text(
            AppLocalizations.of(context).feedbackThanks,
            style: TextStyle(fontSize: 12, color: AppTheme.textMuted),
          ),
        ],
      );
    }
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          icon: const Icon(Icons.thumb_up_outlined, size: 18),
          color: AppTheme.textMuted,
          tooltip: AppLocalizations.of(context).feedbackHelpful,
          onPressed: () => onFeedback('up'),
        ),
        IconButton(
          icon: const Icon(Icons.thumb_down_outlined, size: 18),
          color: AppTheme.textMuted,
          tooltip: AppLocalizations.of(context).feedbackNotHelpful,
          onPressed: () => onFeedback('down'),
        ),
      ],
    );
  }
}

// (No trailing helpers needed — AssistantReply and Domain are used
// explicitly by the Assistant body and metadata chip widget above.)
