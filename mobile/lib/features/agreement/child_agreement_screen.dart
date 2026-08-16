/// The agreement, from the child's side — the only surface that opens before
/// one is signed.
///
/// Each clause is acknowledged on its own. That is the whole design: a single
/// «تمام» for the page is a signature on something unread, which is what
/// paper contracts get wrong and what a seven-year-old will do in two seconds
/// if you let them. The sign button stays disabled until every clause that
/// binds them has been ticked, and the server enforces the same rule so a
/// modified client gains nothing.
///
/// The parent's clauses are shown too, and not as decoration: the child
/// seeing what their parent signed up to is the mechanism. A child who knows
/// «بابا كمان مايجيبش موبايل على السفرة» has something to point at.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/chat_notifier.dart' show tgClientProvider;
import '../routine/services/child_mode_secure_storage.dart';

class ChildAgreementScreen extends ConsumerStatefulWidget {
  const ChildAgreementScreen({super.key});

  @override
  ConsumerState<ChildAgreementScreen> createState() =>
      _ChildAgreementScreenState();
}

class _ChildAgreementScreenState extends ConsumerState<ChildAgreementScreen> {
  Map<String, dynamic>? _agreement;
  final Set<int> _acked = {};
  bool _loading = true;
  bool _done = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  List<Map<String, dynamic>> get _clauses => List<Map<String, dynamic>>.from(
      (_agreement?['clauses'] as List?) ?? const []);

  List<Map<String, dynamic>> get _mine => _clauses
      .where((c) => c['applies_to'] == 'child' || c['applies_to'] == 'both')
      .toList();

  List<Map<String, dynamic>> get _theirs => _clauses
      .where((c) => c['applies_to'] == 'parent' || c['applies_to'] == 'both')
      .toList();

  bool get _allRead => _mine.isNotEmpty &&
      _mine.every((c) => _acked.contains(c['id'] as int) ||
          c['acknowledged_at'] != null);

  Future<void> _load() async {
    final token = await getChildToken();
    if (token == null) {
      setState(() { _loading = false; _error = 'الجلسة انتهت.'; });
      return;
    }
    try {
      final agreement =
          await ref.read(tgClientProvider).fetchChildAgreement(token);
      if (!mounted) return;
      setState(() {
        _agreement = agreement;
        _acked.addAll(_clauses
            .where((c) => c['acknowledged_at'] != null)
            .map((c) => c['id'] as int));
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  Future<void> _ack(int clauseId) async {
    final token = await getChildToken();
    if (token == null) return;
    try {
      await ref.read(tgClientProvider)
          .acknowledgeClause(childToken: token, clauseId: clauseId);
      if (mounted) setState(() => _acked.add(clauseId));
    } catch (_) {
      // A failed tick is not worth an error dialog in a child's face; the
      // button simply stays unticked and they can try again.
    }
  }

  Future<void> _sign() async {
    final token = await getChildToken();
    if (token == null) return;
    setState(() => _loading = true);
    try {
      final activated =
          await ref.read(tgClientProvider).signAgreementAsChild(token);
      if (!mounted) return;
      setState(() { _loading = false; _done = activated; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_done) {
      return Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text('✍️', style: TextStyle(fontSize: 56)),
                const SizedBox(height: 16),
                const Text('اتفقنا 🤝',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                const SizedBox(height: 12),
                const Text(
                  'الميثاق ده بينك وبين أهلك، ومكتوب على الاتنين مش عليك '
                  'لوحدك. هتراجعوه مع بعض بعد شهر.',
                  textAlign: TextAlign.center,
                  style: TextStyle(height: 1.8),
                ),
                const SizedBox(height: 24),
                FilledButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('تمام'),
                ),
              ],
            ),
          ),
        ),
      );
    }
    if (_agreement == null) {
      return Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              _error ?? 'لسه مافيش ميثاق. اطلب من بابا أو ماما يفتحوه معاك.',
              textAlign: TextAlign.center,
              style: const TextStyle(height: 1.8),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('اتفاقنا')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text('اقرا كل بند، ولو فهمته دوس «فهمت».',
              style: TextStyle(height: 1.7, fontWeight: FontWeight.w700)),
          const SizedBox(height: 16),
          for (final c in _mine)
            Card(
              child: ListTile(
                title: Text(c['text_ar'] as String,
                    style: const TextStyle(height: 1.6)),
                trailing: _acked.contains(c['id'] as int)
                    ? const Icon(Icons.check_circle, color: Colors.green)
                    : TextButton(
                        onPressed: () => _ack(c['id'] as int),
                        child: const Text('فهمت'),
                      ),
              ),
            ),
          const SizedBox(height: 20),
          const Text('وده اللي أهلك اتفقوا عليه:',
              style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          for (final c in _theirs)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Text('👤 ${c['text_ar']}',
                  style: const TextStyle(height: 1.6)),
            ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _allRead ? _sign : null,
            child: const Text('أنا موافق'),
          ),
        ],
      ),
    );
  }
}
