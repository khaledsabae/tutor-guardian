/// One chat bubble. User bubbles are teal (right in RTL); assistant
/// bubbles are light grey (left in RTL). Assistant messages render their
/// content as Markdown (light subset) and show streaming/typing states.
library;

import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

// Domain enum is used implicitly via the .labelAr getters on AssistantReply
// — keep the import live.
import '../models/api_models.dart';
import '../state/chat_notifier.dart';
import '../theme/app_theme.dart';
import 'safety_banner.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessageUI message;
  final bool isFirstInGroup;
  final bool isLastInGroup;
  final ValueChanged<String>? onFeedback;

  const MessageBubble({
    super.key,
    required this.message,
    this.isFirstInGroup = true,
    this.isLastInGroup = true,
    this.onFeedback,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final align =
        isUser ? Alignment.centerRight : Alignment.centerLeft;
    final bubbleColor =
        isUser ? AppTheme.primary : AppTheme.surfaceAlt;
    final textColor =
        isUser ? Colors.white : AppTheme.textPrimary;

    final radius = BorderRadius.only(
      topLeft: const Radius.circular(16),
      topRight: const Radius.circular(16),
      bottomLeft: Radius.circular(isUser || isLastInGroup ? 16 : 4),
      bottomRight: Radius.circular(!isUser || isLastInGroup ? 16 : 4),
    );

    final body = Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.84,
      ),
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: bubbleColor,
        borderRadius: radius,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: isUser
          ? Text(
              message.content,
              style: TextStyle(color: textColor, fontSize: 15, height: 1.5),
            )
          : _AssistantBody(
              message: message,
              onFeedback: onFeedback,
            ),
    );

    return Align(
      alignment: align,
      child: Column(
        crossAxisAlignment:
            isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          if (isFirstInGroup) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Text(
                isUser ? '👤 أنت' : '🛡️  المربي',
                style: const TextStyle(
                  fontSize: 11,
                  color: AppTheme.textMuted,
                ),
              ),
            ),
          ],
          body,
          if (message.error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.error_outline,
                      size: 14, color: AppTheme.dangerFg),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      message.error!,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppTheme.dangerFg,
                      ),
                    ),
                  ),
                ],
              ),
            ),
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
    final showContent =
        message.content.isNotEmpty || message.isStreaming;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (r != null) SafetyBanner(reply: r),
        if (showContent)
          MarkdownBody(
            data: message.content.isEmpty ? '…' : message.content,
            styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context))
                .copyWith(
              p: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 15,
                height: 1.6,
              ),
              code: const TextStyle(
                fontFamily: 'monospace',
                backgroundColor: AppTheme.surfaceAlt,
              ),
            ),
          )
        else
          const SizedBox.shrink(),
        if (message.isStreaming)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: _TypingIndicator(),
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
    final chips = <String>[
      reply.domain.labelAr,
      reply.mode.labelAr,
      reply.severity.label,
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
                style: const TextStyle(
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
          const Text(
            'شكراً على تقييمك',
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
          tooltip: 'إجابة مفيدة',
          onPressed: () => onFeedback('up'),
        ),
        IconButton(
          icon: const Icon(Icons.thumb_down_outlined, size: 18),
          color: AppTheme.textMuted,
          tooltip: 'إجابة غير مفيدة',
          onPressed: () => onFeedback('down'),
        ),
      ],
    );
  }
}

// (No trailing helpers needed — AssistantReply and Domain are used
// explicitly by the Assistant body and metadata chip widget above.)
