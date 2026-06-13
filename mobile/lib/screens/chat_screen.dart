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
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/api_models.dart';
import '../models/enums.dart';
import '../state/chat_notifier.dart';
import '../state/connectivity_provider.dart';
import '../theme/app_theme.dart';
import '../theme/design_tokens.dart';
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

class _ChatScreenState extends ConsumerState<ChatScreen>
    with WidgetsBindingObserver {
  final TextEditingController _input = TextEditingController();
  final FocusNode _inputFocus = FocusNode();
  final ScrollController _scroll = ScrollController();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  Future<List<ChatSessionSummary>>? _historyFuture;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Bootstrap the session once the widget is mounted.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(chatNotifierProvider.notifier).bootstrap();
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Leaving the app mid-answer must not lose the partial reply.
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      ref.read(chatNotifierProvider.notifier).onAppPaused();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
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

    // Push the latest online/offline status into the notifier so its
    // `sendMessage` can short-circuit with a friendly Arabic message.
    final connectivity = ref.watch(connectivityProvider);
    final isOnline = connectivity.maybeWhen(
      data: (v) => v,
      orElse: () => true,
    );
    // Update synchronously (the notifier just stores a boolean).
    notifier.setOnline(isOnline);

    return Scaffold(
      key: _scaffoldKey,
      onDrawerChanged: (open) {
        if (open) {
          setState(() => _historyFuture = notifier.loadSessionList());
        }
      },
      drawer: _HistoryDrawer(
        future: _historyFuture,
        currentSessionId: state.sessionId,
        onSelect: (id) async {
          Navigator.of(context).pop(); // close drawer
          await notifier.switchToSession(id);
          _scrollToBottom();
        },
        onNewConversation: () async {
          Navigator.of(context).pop();
          await notifier.startNewConversation();
        },
      ),
      appBar: AppBar(
        leading: IconButton(
          tooltip: 'المحادثات السابقة',
          icon: const Icon(Icons.menu),
          onPressed: () => _scaffoldKey.currentState?.openDrawer(),
        ),
        title: const Text('🛡️  المربي الذكي'),
        actions: [
          if (state.turnCount > 0)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 3,
                  ),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(Dt.rChip),
                  ),
                  child: Text(
                    '${state.turnCount} سؤال',
                    style: const TextStyle(
                      color: AppTheme.primary,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
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
          if (!isOnline) const _OfflineBanner(),
          // Daily tip moved to the Home tab (اليوم) — chat is now a
          // pure conversation surface.
          _SettingsBar(state: state, notifier: notifier),
          if (state.errorBanner != null) _ErrorBanner(
            message: state.errorBanner!,
            onRetry: notifier.retryLastTurn,
          ),
          Expanded(
            child: state.sessionId == null
                ? const _BootSplash()
                : state.messages.isEmpty
                    ? _EmptyState(
                        onSuggest: (q) {
                          _input.text = q;
                          _inputFocus.requestFocus();
                        },
                      )
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
                      // Keyed by message id so the entrance animation
                      // plays exactly once per message — token-by-token
                      // rebuilds of the streaming bubble keep the same
                      // element (and its finished animation state).
                      return KeyedSubtree(
                        key: ValueKey(m.id),
                        child: MessageBubble(
                          message: m,
                          isFirstInGroup:
                              prev == null || prev.role != m.role,
                          isLastInGroup:
                              next == null || next.role != m.role,
                          onFeedback: (rating) {
                            notifier.submitFeedback(m.id, rating);
                          },
                        )
                            .animate()
                            .fadeIn(duration: 250.ms)
                            .slideY(begin: .06, curve: Curves.easeOutCubic),
                      );
                    },
                  ),
          ),
          _Composer(
            controller: _input,
            focusNode: _inputFocus,
            // Always typable now — the user can queue/interrupt while the
            // assistant is still answering.
            enabled: true,
            isStreaming: state.phase == ChatPhase.streaming,
            onSend: _onSend,
            onStop: () =>
                ref.read(chatNotifierProvider.notifier).stopStreaming(),
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

class _BootSplash extends StatelessWidget {
  const _BootSplash();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(strokeWidth: 2),
          SizedBox(height: 12),
          Text(
            'جاري تهيئة الجلسة…',
            style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
          ),
        ],
      ),
    );
  }
}

class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppTheme.warningBg,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: const Row(
        children: [
          Icon(Icons.wifi_off, color: AppTheme.warningFg, size: 18),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              'غير متصل بالإنترنت',
              style: TextStyle(
                color: AppTheme.warningFg,
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final ValueChanged<String> onSuggest;
  const _EmptyState({required this.onSuggest});

  static const _suggestions = [
    'كيف أتعامل مع نوبات الغضب؟',
    'طفلي لا يحب المذاكرة',
    'كيف أعلّم طفلي الصلاة؟',
  ];

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('💬', style: TextStyle(fontSize: 64))
                .animate()
                .scale(
                  begin: const Offset(.6, .6),
                  duration: Dt.slow,
                  curve: Curves.easeOutBack,
                ),
            const SizedBox(height: 12),
            const Text(
              'مرحباً — اسأل عن أي تحدٍّ تربوي يواجهك',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
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
            const SizedBox(height: 20),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                for (var i = 0; i < _suggestions.length; i++)
                  ActionChip(
                    label: Text(_suggestions[i]),
                    labelStyle: const TextStyle(
                      color: AppTheme.primary,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                    backgroundColor:
                        AppTheme.primary.withValues(alpha: .08),
                    side: BorderSide(
                      color: AppTheme.primary.withValues(alpha: .3),
                    ),
                    shape: const StadiumBorder(),
                    onPressed: () => onSuggest(_suggestions[i]),
                  )
                      .animate(delay: (100 * i).ms)
                      .fadeIn(duration: Dt.base)
                      .slideY(begin: .2, curve: Curves.easeOutCubic),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Left drawer listing the device's past conversations so they don't
/// pile up in one endless thread.
class _HistoryDrawer extends StatelessWidget {
  final Future<List<ChatSessionSummary>>? future;
  final String? currentSessionId;
  final ValueChanged<String> onSelect;
  final VoidCallback onNewConversation;

  const _HistoryDrawer({
    required this.future,
    required this.currentSessionId,
    required this.onSelect,
    required this.onNewConversation,
  });

  @override
  Widget build(BuildContext context) {
    return Drawer(
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
              child: Text(
                '💬 محادثاتي',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: ListTile(
                leading: const Icon(Icons.add_circle_outline,
                    color: AppTheme.primary),
                title: const Text(
                  'محادثة جديدة',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: AppTheme.primary,
                  ),
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
                onTap: onNewConversation,
              ),
            ),
            const Divider(height: 16),
            Expanded(
              child: FutureBuilder<List<ChatSessionSummary>>(
                future: future,
                builder: (context, snap) {
                  if (snap.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  final sessions = snap.data ?? const [];
                  if (sessions.isEmpty) {
                    return const Center(
                      child: Padding(
                        padding: EdgeInsets.all(24),
                        child: Text(
                          'لا توجد محادثات سابقة بعد',
                          style: TextStyle(color: AppTheme.textMuted),
                        ),
                      ),
                    );
                  }
                  return ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    itemCount: sessions.length,
                    itemBuilder: (context, i) {
                      final s = sessions[i];
                      final active = s.id == currentSessionId;
                      return ListTile(
                        selected: active,
                        selectedTileColor:
                            AppTheme.primary.withValues(alpha: .08),
                        leading:
                            const Icon(Icons.chat_bubble_outline, size: 20),
                        title: Text(
                          s.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 14),
                        ),
                        subtitle: Text('${s.messageCount} رسالة'),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                        onTap: () => onSelect(s.id),
                      );
                    },
                  );
                },
              ),
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
  final bool isStreaming;
  final VoidCallback onSend;
  final VoidCallback onStop;
  const _Composer({
    required this.controller,
    required this.focusNode,
    required this.enabled,
    required this.isStreaming,
    required this.onSend,
    required this.onStop,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(Dt.rSheet),
                  boxShadow: Dt.cardShadow,
                ),
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
                    filled: false,
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    contentPadding:
                        EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                    isDense: true,
                  ),
                  inputFormatters: [
                    LengthLimitingTextInputFormatter(2000),
                  ],
                ),
              ),
            ),
            const SizedBox(width: 8),
            // While streaming → red stop button; otherwise → send.
            GestureDetector(
              onTap: isStreaming ? onStop : (enabled ? onSend : null),
              child: Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  gradient: isStreaming ? null : Dt.primaryGradient,
                  color: isStreaming ? AppTheme.dangerFg : null,
                  shape: BoxShape.circle,
                  boxShadow: Dt.softShadow(
                    isStreaming ? AppTheme.dangerFg : Dt.primary,
                    alpha: .3,
                  ),
                ),
                child: Icon(
                  // Icons.send auto-mirrors under RTL Directionality.
                  isStreaming ? Icons.stop_rounded : Icons.send,
                  color: Colors.white,
                  size: 22,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
