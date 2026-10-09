/// Main chat screen — Phase 3 deliverable.
///
/// Layout:
///   * AppBar  : "🛡️  المربي الذكي"  +  badge with turn count.
///   * Context chip : the optional behavior_type, folded into the composer
///                    (UX_UI_ROADMAP C6) — no permanent bar above the chat.
///   * Message list : user bubbles (right) + assistant bubbles (left) +
///                    safety banners driven by AssistantReply flags.
///   * Composer     : auto-grow textarea + send button (disabled while
///                    streaming) + Enter-to-send.
///   * New conversation button + retry button (on error).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/haptics.dart';
import '../models/api_models.dart';
import '../models/enums.dart';
import '../features/onboarding/providers/onboarding_providers.dart';
import '../features/program/providers/program_providers.dart';
import '../features/program/providers/progress_providers.dart'
    show activeChildIdProvider;
import '../state/chat_notifier.dart';
import '../state/connectivity_provider.dart';
import '../theme/app_theme.dart';
import '../theme/design_tokens.dart';
import '../widgets/message_bubble.dart';
import '../l10n/app_localizations.dart';
import 'package:almorabbi/widgets/ui/loading_view.dart';

final chatNotifierProvider =
    StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final client = ref.watch(tgClientProvider);
  // Read at send time, not watched: switching child must not rebuild the
  // notifier and drop the conversation on screen.
  return ChatNotifier(client,
      activeChildId: () => ref.read(activeChildIdProvider));
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

  /// "↓ Latest reply" is offered once the reader has scrolled this far above
  /// the bottom (UX_UI_ROADMAP C10).
  static const double _jumpThreshold = 300;
  final ValueNotifier<bool> _showJump = ValueNotifier(false);

  void _onScroll() {
    if (!_scroll.hasClients) return;
    final pos = _scroll.position;
    _showJump.value = pos.maxScrollExtent - pos.pixels > _jumpThreshold;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _scroll.addListener(_onScroll);
    // Bootstrap the session once the widget is mounted.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final notifier = ref.read(chatNotifierProvider.notifier);
      notifier.setOnline(
        ref.read(connectivityProvider).maybeWhen(data: (v) => v, orElse: () => true),
      );
      notifier.bootstrap();
      // A question seeded before this screen existed (onboarding's deferred
      // «ask the mentor»): the listen below only fires on *changes*, so a
      // value set while the chat was not yet mounted would be silently
      // dropped. Consume whatever is already there, exactly once.
      final seeded = ref.read(pendingChatQuestionProvider);
      if (seeded != null && seeded.trim().isNotEmpty) {
        _consumePendingQuestion(seeded);
      }
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final notifier = ref.read(chatNotifierProvider.notifier);
    // Leaving the app saves the conversation but no longer stops a streaming
    // answer (see ChatNotifier.onAppPaused); coming back recovers one whose
    // connection the OS cut meanwhile.
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      notifier.onAppPaused();
    } else if (state == AppLifecycleState.resumed) {
      notifier.onAppResumed();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _input.dispose();
    _inputFocus.dispose();
    _scroll.removeListener(_onScroll);
    _scroll.dispose();
    _showJump.dispose();
    super.dispose();
  }

  /// Keep the answer in view while it streams — but only if the reader is
  /// already at (or near) the bottom. Scrolling back up to reread something
  /// must not be yanked away by the next token.
  void _followStream() {
    if (!_scroll.hasClients) return;
    final pos = _scroll.position;
    if (pos.maxScrollExtent - pos.pixels > 120) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
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

  /// Sends a seeded question and clears the seed — shared by the listener
  /// (question arrives while the chat is live) and the initState bootstrap
  /// (question arrived before the chat mounted).
  void _consumePendingQuestion(String question) {
    ref.read(pendingChatQuestionProvider.notifier).state = null;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      if (!mounted) return;
      await ref.read(chatNotifierProvider.notifier).sendMessage(question);
      _scrollToBottom();
    });
  }

  Future<void> _onSend() async {
    final text = _input.text;
    if (text.trim().isEmpty) return;
    _input.clear();
    unawaited(Haptics.selection());
    await ref.read(chatNotifierProvider.notifier).sendMessage(text);
    _scrollToBottom();
  }

  /// The optional behaviour type ("context") used to sit in a permanent
  /// field above the conversation, ~64 dp that mattered most with the
  /// keyboard up. It is now a sheet opened from the composer (C6).
  Future<void> _editContext(String current) async {
    final value = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _ContextSheet(initial: current),
    );
    if (value == null || !mounted) return;
    ref.read(chatNotifierProvider.notifier).setBehaviorType(value.trim());
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(chatNotifierProvider);
    final notifier = ref.read(chatNotifierProvider.notifier);

    // The active child's age drives the question — there's no manual age
    // selector. Keep the chat state in sync whenever the active child changes.
    final activeAge = AgeGroup.fromWire(ref.watch(selectedAgeGroupProvider));
    if (state.ageGroup != activeAge) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) notifier.setAgeGroup(activeAge);
      });
    }

    // Auto-scroll on every message change.
    ref.listen<ChatState>(chatNotifierProvider, (prev, next) {
      if ((prev?.messages.length ?? 0) != next.messages.length) {
        _scrollToBottom();
      } else if (next.phase == ChatPhase.streaming &&
          next.messages.isNotEmpty &&
          prev != null &&
          prev.messages.isNotEmpty &&
          prev.messages.last.content.length !=
              next.messages.last.content.length) {
        // The count only changes when a turn starts, so tokens growing the
        // last bubble used to run below the fold unseen.
        _followStream();
      }
    });

    // A question seeded from outside the chat (e.g. «اسأل المربّي عن ده» on the
    // coach-tip card). Auto-send it once, then clear so it never re-fires.
    ref.listen<String?>(pendingChatQuestionProvider, (prev, next) {
      if (next == null || next.trim().isEmpty) return;
      _consumePendingQuestion(next);
    });

    // Push online/offline changes into the notifier so its `sendMessage` can
    // short-circuit with a friendly message. A listener, not a call in build:
    // build must not have side effects (the initial value is pushed from
    // initState's post-frame callback).
    ref.listen<AsyncValue<bool>>(connectivityProvider, (_, next) {
      notifier.setOnline(next.maybeWhen(data: (v) => v, orElse: () => true));
    });

    // One error surface per failure: when the failed turn already shows its
    // error inline (with Retry), the top banner would repeat the same text.
    final lastError = state.messages.isEmpty ? null : state.messages.last.error;
    final showBanner = state.errorBanner != null && state.errorBanner != lastError;

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
          tooltip: AppLocalizations.of(context).chatPrevChats,
          icon: const Icon(Icons.menu),
          onPressed: () => _scaffoldKey.currentState?.openDrawer(),
        ),
        title: Text(AppLocalizations.of(context).chatTitle),
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
                    AppLocalizations.of(context).chatTurnsCount(state.turnCount),
                    style: TextStyle(
                      color: AppTheme.primary,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ),
          IconButton(
            tooltip: AppLocalizations.of(context).chatNewConversation,
            icon: const Icon(Icons.refresh),
            onPressed: state.phase == ChatPhase.streaming
                ? null
                : () async {
                    final confirm = await showDialog<bool>(
                      context: context,
                      builder: (ctx) => AlertDialog(
                        title: Text(AppLocalizations.of(context).chatNewConfirmTitle),
                        content: Text(AppLocalizations.of(context).chatNewConfirmDesc),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(ctx, false),
                            child: Text(AppLocalizations.of(context).chatCancel),
                          ),
                          FilledButton(
                            onPressed: () => Navigator.pop(ctx, true),
                            child: Text(AppLocalizations.of(context).chatContinue),
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
          // Offline is shown app-wide now (AppStatusBanner, E2).
          // Daily tip moved to the Home tab (اليوم) — chat is now a
          // pure conversation surface.
          if (showBanner) _ErrorBanner(
            message: state.errorBanner!,
            onRetry: notifier.retryLastTurn,
          ),
          Expanded(
            child: state.sessionId == null
                ? const _BootSplash()
                : state.messages.isEmpty
                    ? _EmptyState(
                        ageGroup: ref
                            .watch(activeChildProfileProvider)
                            ?.ageGroup,
                        // One tap = question sent — the fastest path to the
                        // first "wow" answer (no typing, no second tap).
                        onSuggest: (q) => notifier.sendMessage(q),
                      )
                    : Stack(
                    children: [
                    ListView.builder(
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
                          onRetry: next == null && m.error != null
                              ? notifier.retryLastTurn
                              : null,
                          followUps: next == null &&
                                  state.phase == ChatPhase.idle
                              ? _followUpsFor(m, AppLocalizations.of(context))
                              : const [],
                          onFollowUp: (q) {
                            unawaited(Haptics.selection());
                            notifier.sendMessage(q);
                          },
                        )
                            .animate()
                            .fadeIn(duration: 250.ms)
                            .slideY(begin: .06, curve: Curves.easeOutCubic),
                      );
                    },
                  ),
                    PositionedDirectional(
                      bottom: Dt.s12,
                      start: 0,
                      end: 0,
                      child: ValueListenableBuilder<bool>(
                        valueListenable: _showJump,
                        builder: (context, show, _) => IgnorePointer(
                          ignoring: !show,
                          child: AnimatedOpacity(
                            opacity: show ? 1 : 0,
                            duration: Dt.fast,
                            child: Center(
                              child: ActionChip(
                                avatar: Icon(Icons.arrow_downward_rounded,
                                    size: 16, color: AppTheme.onPrimary),
                                label: Text(
                                    AppLocalizations.of(context).chatJumpLatest),
                                labelStyle: TextStyle(
                                  color: AppTheme.onPrimary,
                                  fontWeight: FontWeight.w700,
                                ),
                                backgroundColor: AppTheme.primary,
                                side: BorderSide.none,
                                shape: const StadiumBorder(),
                                onPressed: _scrollToBottom,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                    ],
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
                ref.read(chatNotifierProvider.notifier).stopStreaming(notifyServer: true),
            behaviorType: state.behaviorType,
            onEditContext: () => _editContext(state.behaviorType),
            onClearContext: () => notifier.setBehaviorType(''),
          ),
        ],
      ),
    );
  }
}

/// Follow-up chips for the latest finished answer (UX_UI_ROADMAP §2.3).
///
/// Only on real guidance: never under a safety escalation, a refusal or the
/// fiqh referral, where "give me an example" would be the wrong next step.
/// Server-suggested questions win; otherwise three generic, always-valid ones.
List<String> _followUpsFor(ChatMessageUI m, AppLocalizations l10n) {
  final r = m.reply;
  if (m.role != 'assistant' || r == null || m.error != null) return const [];
  if (r.isEmergency || r.isBanned) return const [];
  if (r.mode != ReplyMode.llmGenerated && r.mode != ReplyMode.retrievalOnly) {
    return const [];
  }
  if (r.followUps.isNotEmpty) return r.followUps;
  return [l10n.chatFollowExample, l10n.chatFollowForAge, l10n.chatFollowShort];
}

/// Bottom sheet for the optional behaviour type. Pops with the new value
/// (empty = cleared), or null when dismissed without a change.
class _ContextSheet extends StatefulWidget {
  const _ContextSheet({required this.initial});

  final String initial;

  @override
  State<_ContextSheet> createState() => _ContextSheetState();
}

class _ContextSheetState extends State<_ContextSheet> {
  late final TextEditingController _ctrl =
      TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(
        Dt.s16,
        0,
        Dt.s16,
        Dt.s16 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(l10n.chatContextTitle,
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: Dt.s8),
          TextField(
            controller: _ctrl,
            autofocus: true,
            maxLength: 200, // UserMessage.behavior_type max_length
            textInputAction: TextInputAction.done,
            onSubmitted: (v) => Navigator.pop(context, v),
            decoration: InputDecoration(
              labelText: l10n.chatBehaviorOptional,
              hintText: l10n.chatContextHint,
            ),
          ),
          const SizedBox(height: Dt.s8),
          Row(
            children: [
              if (widget.initial.isNotEmpty)
                TextButton(
                  onPressed: () => Navigator.pop(context, ''),
                  child: Text(l10n.chatContextClear),
                ),
              const Spacer(),
              FilledButton(
                onPressed: () => Navigator.pop(context, _ctrl.text),
                child: Text(l10n.chatContextDone),
              ),
            ],
          ),
        ],
      ),
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
          Icon(Icons.warning_amber_rounded,
              color: AppTheme.dangerFg, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: AppTheme.dangerFg,
                fontSize: 13,
              ),
            ),
          ),
          TextButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 16),
            label: Text(AppLocalizations.of(context).chatRetry),
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
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(strokeWidth: 2),
          const SizedBox(height: 12),
          Text(
            AppLocalizations.of(context).chatInit,
            style: TextStyle(color: AppTheme.textMuted, fontSize: 13),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  final ValueChanged<String> onSuggest;
  final String? ageGroup;
  const _EmptyState({required this.onSuggest, this.ageGroup});

  // Age-tailored pain questions. Topics deliberately match the backend's
  // curated topic seeds (صلاة/مذاكرة/شاشة/عناد/نوم/كذب/سوشيال) so the very
  // first answer lands grounded and specific.
  //
  // Three slots were re-pointed on 2026-08-13 from measured demand: 1,284
  // real questions in production (after excluding these very suggestions,
  // which otherwise dominate any frequency count, and sub-12-character
  // noise). Fear/anxiety (29 questions), sibling jealousy (15) and body
  // changes/privacy (15) each had *zero* suggestion coverage, while the
  // slots they replaced drew 7–9 questions each. The benched keys stay
  // defined below — they are still good questions, just out-competed.
  List<String> _suggestionsFor(AppLocalizations l10n) {
    const ageMap = <String, List<String>>{
      '0-3': ['chatQ_sleep', 'chatQ_stubborn', 'chatQ_siblings'],
      '2-3': ['chatQ_sleep', 'chatQ_stubborn', 'chatQ_speech'],
      '4-6': ['chatQ_pray5', 'chatQ_tantrums', 'chatQ_screens'],
      '7-9': ['chatQ_study', 'chatQ_prayRegular', 'chatQ_fears'],
      '10-12': ['chatQ_gaming', 'chatQ_online', 'chatQ_bodyChanges'],
      '13-15': ['chatQ_teenDefiant', 'chatQ_socialMedia', 'chatQ_teenPray'],
      '16-18': ['chatQ_talkOlder', 'chatQ_university', 'chatQ_friends'],
    };
    const fallback = ['chatQ_tantrums', 'chatQ_study', 'chatQ_pray5'];
    final keys = ageMap[ageGroup] ?? fallback;
    return keys.map((k) => _resolveKey(l10n, k)).toList();
  }

  String _resolveKey(AppLocalizations l10n, String key) {
    switch (key) {
      case 'chatQ_sleep': return l10n.chatQ_sleep;
      case 'chatQ_stubborn': return l10n.chatQ_stubborn;
      case 'chatQ_eating': return l10n.chatQ_eating;
      case 'chatQ_speech': return l10n.chatQ_speech;
      case 'chatQ_pray5': return l10n.chatQ_pray5;
      case 'chatQ_tantrums': return l10n.chatQ_tantrums;
      case 'chatQ_screens': return l10n.chatQ_screens;
      case 'chatQ_study': return l10n.chatQ_study;
      case 'chatQ_prayRegular': return l10n.chatQ_prayRegular;
      case 'chatQ_lying': return l10n.chatQ_lying;
      case 'chatQ_gaming': return l10n.chatQ_gaming;
      case 'chatQ_online': return l10n.chatQ_online;
      case 'chatQ_homework': return l10n.chatQ_homework;
      case 'chatQ_teenDefiant': return l10n.chatQ_teenDefiant;
      case 'chatQ_socialMedia': return l10n.chatQ_socialMedia;
      case 'chatQ_teenPray': return l10n.chatQ_teenPray;
      case 'chatQ_talkOlder': return l10n.chatQ_talkOlder;
      case 'chatQ_university': return l10n.chatQ_university;
      case 'chatQ_friends': return l10n.chatQ_friends;
      case 'chatQ_fears': return l10n.chatQ_fears;
      case 'chatQ_siblings': return l10n.chatQ_siblings;
      case 'chatQ_bodyChanges': return l10n.chatQ_bodyChanges;
      default: return key;
    }
  }

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
            Text(
              AppLocalizations.of(context).chatEmptyWelcome,
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: AppTheme.textPrimary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              AppLocalizations.of(context).chatEmptyHint,
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            Builder(builder: (context) {
              final suggestions = _suggestionsFor(AppLocalizations.of(context));
              return Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: [
                for (var i = 0; i < suggestions.length; i++)
                  ActionChip(
                    label: Text(suggestions[i]),
                    labelStyle: TextStyle(
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
                    onPressed: () => onSuggest(suggestions[i]),
                  )
                      .animate(delay: (100 * i).ms)
                      .fadeIn(duration: Dt.base)
                      .slideY(begin: .2, curve: Curves.easeOutCubic),
              ],
            );
            }),
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
                AppLocalizations.of(context).chatMyChats,
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: ListTile(
                leading: Icon(Icons.add_circle_outline,
                    color: AppTheme.primary),
                title: Text(
                  AppLocalizations.of(context).chatNewChatBtn,
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
                    return const LoadingView(count: 5, itemHeight: 56);
                  }
                  final sessions = snap.data ?? const [];
                  if (sessions.isEmpty) {
                    return Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Text(
                          AppLocalizations.of(context).chatNoChatsYet,
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
                        subtitle: Text(AppLocalizations.of(context).chatSessionMessages(s.messageCount)),
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
  final String behaviorType;
  final VoidCallback onEditContext;
  final VoidCallback onClearContext;
  const _Composer({
    required this.controller,
    required this.focusNode,
    required this.enabled,
    required this.isStreaming,
    required this.onSend,
    required this.onStop,
    required this.behaviorType,
    required this.onEditContext,
    required this.onClearContext,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final hasContext = behaviorType.isNotEmpty;
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Column(
         mainAxisSize: MainAxisSize.min,
         crossAxisAlignment: CrossAxisAlignment.start,
         children: [
          // Takes space only while a context is set.
          if (hasContext)
            Padding(
              padding: const EdgeInsets.only(bottom: Dt.s8),
              child: InputChip(
                avatar: Icon(Icons.tune_rounded,
                    size: 16, color: AppTheme.primary),
                label: ConstrainedBox(
                  constraints: BoxConstraints(
                    maxWidth: MediaQuery.sizeOf(context).width * 0.6,
                  ),
                  child: Text(behaviorType,
                      maxLines: 1, overflow: TextOverflow.ellipsis),
                ),
                tooltip: l10n.chatBehaviorOptional,
                onPressed: onEditContext,
                onDeleted: onClearContext,
                deleteButtonTooltipMessage: l10n.chatContextClear,
              ),
            ),
          Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            IconButton(
              tooltip: l10n.chatContextAdd,
              onPressed: onEditContext,
              icon: Icon(Icons.tune_rounded,
                  color: hasContext ? AppTheme.primary : AppTheme.textMuted),
            ),
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
                  decoration: InputDecoration(
                    hintText: AppLocalizations.of(context).chatTypeHint,
                    filled: false,
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    contentPadding:
                        const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
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
            // A bare GestureDetector is unnamed to a screen reader and has no
            // long-press hint; Semantics + Tooltip give it both.
            Semantics(
              button: true,
              enabled: isStreaming || enabled,
              onTap: isStreaming ? onStop : (enabled ? onSend : null),
              excludeSemantics: true,
              label: isStreaming
                  ? AppLocalizations.of(context).chatStop
                  : l10n.a11ySendQuestion,
              child: Tooltip(
                message: isStreaming
                    ? AppLocalizations.of(context).chatStop
                    : l10n.a11ySendQuestion,
                child: GestureDetector(
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
                      color: Dt.surface,
                      size: 22,
                    ),
                  ),
                ),
              ),
            ),
          ],
          ),
         ],
        ),
      ),
    );
  }
}
