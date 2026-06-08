/// Main chat screen — Phase 3 deliverable.
///
/// Layout:
///   * AppBar  : "🛡️  المربي الذكي"  +  badge with turn count.
///   * Settings bar : age group + severity dropdowns + behavior_type field.
///   * Message list : user bubbles (right) + assistant bubbles (left) +
///                    safety banners driven by AssistantReply flags.
///   * Composer     : auto-grow textarea + send button (disabled while
///                    streaming) + Enter-to-send.
///   * New conversation button + retry button (on error).
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/enums.dart';
import '../state/chat_notifier.dart';
import '../theme/app_theme.dart';
import '../widgets/message_bubble.dart';

final chatNotifierProvider =
    StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final client = ref.watch(tgClientProvider);
  return ChatNotifier(client);
});

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final TextEditingController _input = TextEditingController();
  final FocusNode _inputFocus = FocusNode();
  final ScrollController _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    // Bootstrap the session once the widget is mounted.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(chatNotifierProvider.notifier).bootstrap();
    });
  }

  @override
  void dispose() {
    _input.dispose();
    _inputFocus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (!_scroll.hasClients) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _onSend() async {
    final text = _input.text;
    if (text.trim().isEmpty) return;
    _input.clear();
    await ref.read(chatNotifierProvider.notifier).sendMessage(text);
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatNotifierProvider);
    final notifier = ref.read(chatNotifierProvider.notifier);

    // Auto-scroll on every message change.
    ref.listen<ChatState>(chatNotifierProvider, (prev, next) {
      if ((prev?.messages.length ?? 0) != next.messages.length) {
        _scrollToBottom();
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('🛡️  المربي الذكي'),
        actions: [
          if (state.turnCount > 0)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${state.turnCount} سؤال',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 12,
                    ),
                  ),
                ),
              ),
            ),
          IconButton(
            tooltip: 'بدء محادثة جديدة',
            icon: const Icon(Icons.refresh),
            onPressed: state.phase == ChatPhase.streaming
                ? null
                : () async {
                    final confirm = await showDialog<bool>(
                      context: context,
                      builder: (ctx) => AlertDialog(
                        title: const Text('بدء محادثة جديدة؟'),
                        content: const Text(
                            'سيتم إنهاء المحادثة الحالية وبدء جلسة جديدة على الخادم.'),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(ctx, false),
                            child: const Text('إلغاء'),
                          ),
                          FilledButton(
                            onPressed: () => Navigator.pop(ctx, true),
                            child: const Text('متابعة'),
                          ),
                        ],
                      ),
                    );
                    if (confirm == true) {
                      await notifier.startNewConversation();
                    }
                  },
          ),
        ],
      ),
      body: Column(
        children: [
          _SettingsBar(state: state, notifier: notifier),
          if (state.errorBanner != null) _ErrorBanner(
            message: state.errorBanner!,
            onRetry: notifier.retryLastTurn,
          ),
          Expanded(
            child: state.messages.isEmpty
                ? const _EmptyState()
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: state.messages.length,
                    itemBuilder: (context, i) {
                      final m = state.messages[i];
                      final prev = i > 0 ? state.messages[i - 1] : null;
                      final next = i + 1 < state.messages.length
                          ? state.messages[i + 1]
                          : null;
                      return MessageBubble(
                        message: m,
                        isFirstInGroup: prev == null || prev.role != m.role,
                        isLastInGroup: next == null || next.role != m.role,
                        onFeedback: (rating) {
                          notifier.submitFeedback(m.id, rating);
                        },
                      );
                    },
                  ),
          ),
          _Composer(
            controller: _input,
            focusNode: _inputFocus,
            enabled: state.phase != ChatPhase.streaming,
            onSend: _onSend,
          ),
        ],
      ),
    );
  }
}

class _SettingsBar extends StatelessWidget {
  final ChatState state;
  final ChatNotifier notifier;
  const _SettingsBar({required this.state, required this.notifier});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        border: Border(
          bottom: BorderSide(color: AppTheme.surfaceAlt, width: 1),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: _DropdownField<AgeGroup>(
              label: 'العمر',
              value: state.ageGroup,
              items: AgeGroup.values,
              labelOf: (g) => g.label,
              onChanged: (g) {
                if (g != null) notifier.setAgeGroup(g);
              },
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _DropdownField<Severity>(
              label: 'الشدة',
              value: state.severity,
              items: Severity.values,
              labelOf: (s) => s.label,
              onChanged: (s) {
                if (s != null) notifier.setSeverity(s);
              },
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 2,
            child: TextFormField(
              initialValue: state.behaviorType,
              decoration: const InputDecoration(
                labelText: 'نوع السلوك (اختياري)',
                isDense: true,
              ),
              textInputAction: TextInputAction.done,
              onChanged: notifier.setBehaviorType,
            ),
          ),
        ],
      ),
    );
  }
}

class _DropdownField<T> extends StatelessWidget {
  final String label;
  final T value;
  final List<T> items;
  final String Function(T) labelOf;
  final ValueChanged<T?> onChanged;
  const _DropdownField({
    required this.label,
    required this.value,
    required this.items,
    required this.labelOf,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<T>(
      initialValue: value,
      isExpanded: true,
      isDense: true,
      decoration: InputDecoration(labelText: label, isDense: true),
      items: items
          .map((it) => DropdownMenuItem<T>(
                value: it,
                child: Text(labelOf(it), overflow: TextOverflow.ellipsis),
              ))
          .toList(),
      onChanged: onChanged,
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorBanner({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppTheme.dangerBg,
      padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded,
              color: AppTheme.dangerFg, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: AppTheme.dangerFg,
                fontSize: 13,
              ),
            ),
          ),
          TextButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('إعادة المحاولة'),
            style: TextButton.styleFrom(foregroundColor: AppTheme.dangerFg),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.shield_outlined,
                size: 72, color: AppTheme.primary.withValues(alpha: 0.7)),
            const SizedBox(height: 12),
            const Text(
              'مرحباً — اسأل عن أي تحدٍّ تربوي يواجهك',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.textPrimary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            const Text(
              'اختر الفئة العمرية والشدة من الشريط أعلاه، ثم اكتب سؤالك.',
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final bool enabled;
  final VoidCallback onSend;
  const _Composer({
    required this.controller,
    required this.focusNode,
    required this.enabled,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Container(
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          border: Border(
            top: BorderSide(color: AppTheme.surfaceAlt, width: 1),
          ),
        ),
        padding: const EdgeInsets.fromLTRB(8, 8, 8, 8),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                enabled: enabled,
                minLines: 1,
                maxLines: 5,
                textInputAction: TextInputAction.send,
                onSubmitted: enabled ? (_) => onSend() : null,
                decoration: const InputDecoration(
                  hintText: 'اكتب سؤالك…',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                inputFormatters: [
                  LengthLimitingTextInputFormatter(2000),
                ],
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              onPressed: enabled ? onSend : null,
              icon: const Icon(Icons.send),
              tooltip: 'إرسال',
            ),
          ],
        ),
      ),
    );
  }
}
