/// The internet licence, as a child sees it: one situation, three answers.
///
/// There is no text field here and there will not be one. Scenario training
/// does not need free input — the situation is described and the child picks —
/// and that single decision is what keeps `allow_free_text` false, keeps the
/// two loader guards untouched, and removes the topic whitelist from the
/// critical path entirely. See plans/sprint3-internet-licence-spec.md §1.2.
///
/// **Nothing here tells the child whether they were right.** Not a colour, not
/// a tick, not a "try again". Echo the verdict back and the exercise becomes a
/// puzzle to brute-force until the green light appears — which measures
/// persistence, not judgement. The child answers, gets a quiet acknowledgement
/// pointing at a conversation with their parent, and moves on.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/tg_client.dart';
import '../../l10n/app_localizations.dart';
import '../../state/chat_notifier.dart';
import '../routine/providers/child_mode_providers.dart';
import '../routine/services/child_mode_secure_storage.dart';
import '../routine/widgets/quiet_time_bar.dart';

class ChildLicenseScreen extends ConsumerStatefulWidget {
  const ChildLicenseScreen({super.key});

  @override
  ConsumerState<ChildLicenseScreen> createState() => _ChildLicenseScreenState();
}

class _ChildLicenseScreenState extends ConsumerState<ChildLicenseScreen> {
  Map<String, dynamic>? _payload;
  bool _loading = true;
  bool _sending = false;

  /// Shown after an answer: an acknowledgement, not a verdict.
  bool _acknowledged = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final token = await getChildToken();
    if (token == null) {
      if (mounted) setState(() => _loading = false);
      return;
    }
    try {
      final data = await ref.read(tgClientProvider).fetchChildLicense(token);
      if (mounted) setState(() { _payload = data; _loading = false; });
    } on TgApiError {
      // A child gets no error dialog. An unreachable server looks like a day
      // with nothing to practise, which is a state they already understand.
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _choose(String scenarioKey, String choiceKey) async {
    final token = await getChildToken();
    if (token == null || _sending) return;
    setState(() => _sending = true);
    try {
      await ref.read(tgClientProvider).answerLicenseScenario(
            childToken: token,
            scenarioKey: scenarioKey,
            choiceKey: choiceKey,
          );
    } on TgApiError {
      // Swallowed. Telling a child the network disagreed with their answer
      // teaches them the app is the authority on their own judgement.
    }
    if (!mounted) return;
    setState(() { _sending = false; _acknowledged = true; });
  }

  Future<void> _next() async {
    setState(() { _acknowledged = false; _loading = true; });
    await _load();
  }

  Future<void> _leave() async {
    await ref.read(childModeProvider.notifier).endSession(reason: 'completed');
    if (mounted) Navigator.of(context).maybePop();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final l10n = AppLocalizations.of(context);

    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    final scenario = _payload?['scenario'] as Map<String, dynamic>?;

    // Acknowledgement. Deliberately identical whatever was chosen — the same
    // words for the answer we hoped for and the one we did not.
    if (_acknowledged) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('🤝', style: theme.textTheme.displayMedium),
                  const SizedBox(height: 16),
                  Text(
                    l10n.licenseAckTitle,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.titleMedium?.copyWith(height: 1.6),
                  ),
                  const SizedBox(height: 28),
                  FilledButton(
                    onPressed: _next,
                    style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(56)),
                    child: Text(l10n.licenseAckNext),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    // Nothing left in this level: practice done, and what happens next is a
    // conversation, not another screen.
    if (scenario == null) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('🌙', style: theme.textTheme.displayMedium),
                  const SizedBox(height: 16),
                  Text(
                    l10n.licenseDoneTitle,
                    textAlign: TextAlign.center,
                    style: theme.textTheme.titleMedium?.copyWith(height: 1.6),
                  ),
                  const SizedBox(height: 28),
                  FilledButton(
                    onPressed: _leave,
                    style: FilledButton.styleFrom(
                        minimumSize: const Size.fromHeight(56)),
                    child: Text(l10n.licenseLeave),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    final choices =
        (scenario['choices'] as List<dynamic>).cast<Map<String, dynamic>>();

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const QuietTimeBar(),
              const Spacer(),
              Text('🧭', style: theme.textTheme.displayLarge,
                  textAlign: TextAlign.center),
              const SizedBox(height: 20),
              Text(
                scenario['situation_ar'] as String? ?? '',
                textAlign: TextAlign.center,
                style: theme.textTheme.titleMedium?.copyWith(height: 1.8),
              ),
              const Spacer(),
              // All three rendered identically — same colour, same weight,
              // same order every time. A styled "right" answer is an answer
              // key, and a child learns to read the styling instead of the
              // situation.
              for (final choice in choices)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: OutlinedButton(
                    onPressed: _sending
                        ? null
                        : () => _choose(scenario['key'] as String,
                            choice['key'] as String),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size.fromHeight(60),
                      alignment: AlignmentDirectional.centerStart,
                      padding: const EdgeInsets.symmetric(horizontal: 18),
                    ),
                    child: Text(
                      choice['text_ar'] as String? ?? '',
                      textAlign: TextAlign.start,
                      style: theme.textTheme.bodyLarge,
                    ),
                  ),
                ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }
}
