/// The family media agreement, from the parent's side.
///
/// This screen is a release blocker for the agreement gate: since the server
/// refuses every child surface until an agreement is signed, a family with no
/// way to sign has no child mode at all.
///
/// The clause list is deliberately not two columns of ticks. Each pair is one
/// card showing the child's clause and the parent's answer to it together,
/// because the trade is the content — a parent who unticks «أسمع من غير ما
/// أزعّق» while keeping «أقول لبابا» should see what they just did.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/chat_notifier.dart' show tgClientProvider;
import '../program/providers/progress_providers.dart' show activeChildIdProvider;
import 'agreement_export.dart';
import 'signature_pad.dart';

class AgreementScreen extends ConsumerStatefulWidget {
  const AgreementScreen({super.key, this.childName = 'ابنك'});

  final String childName;

  @override
  ConsumerState<AgreementScreen> createState() => _AgreementScreenState();
}

class _AgreementScreenState extends ConsumerState<AgreementScreen> {
  final _boundaryKey = GlobalKey();
  final _signatureKey = GlobalKey<SignaturePadState>();

  List<Map<String, dynamic>> _pairs = [];
  final Set<String> _excluded = {};
  Map<String, dynamic>? _agreement;
  bool _loading = true;
  bool _signed = false;
  bool _hasSignature = false;
  String? _error;

  int? get _childId => ref.read(activeChildIdProvider);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final childId = _childId;
    if (childId == null) {
      setState(() {
        _loading = false;
        _error = 'اختر طفلاً أولاً.';
      });
      return;
    }
    try {
      final client = ref.read(tgClientProvider);
      final existing = await client.fetchAgreement(childId);
      final suggested = await client.fetchSuggestedClauses(childId);
      if (!mounted) return;
      setState(() {
        _agreement = existing;
        _signed = existing?['status'] == 'active';
        _pairs = List<Map<String, dynamic>>.from(suggested['pairs'] as List);
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  List<Map<String, dynamic>> _clausesToSend() {
    final out = <Map<String, dynamic>>[];
    var order = 0;
    for (final pair in _pairs) {
      final key = pair['key'] as String?;
      if (_excluded.contains(key)) continue;
      out.add({'applies_to': 'child', 'clause_key': key,
               'text_ar': pair['child'], 'sort_order': order++});
      out.add({'applies_to': 'parent', 'clause_key': key,
               'text_ar': pair['parent'], 'sort_order': order++});
    }
    return out;
  }

  Future<void> _saveAndSign() async {
    final childId = _childId;
    if (childId == null) return;
    final clauses = _clausesToSend();
    if (clauses.isEmpty) {
      // Only one state can reach here now: a parent who unticked every pair.
      // The empty-bank case renders its own explanation on arrival and never
      // shows this button at all — putting the explanation behind a press was
      // the bug in 1.0.43.
      setState(() => _error = 'اخترت إنك تشيل كل البنود. سيب بند واحد على الأقل.');
      return;
    }
    setState(() { _loading = true; _error = null; });
    try {
      final client = ref.read(tgClientProvider);
      final draft = await client.saveAgreementDraft(childId, clauses);
      await client.signAgreementAsParent(childId);
      if (!mounted) return;
      setState(() { _agreement = draft; _loading = false; });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('وقّعت. فاضل توقيع ابنك من وضع الطفل.'),
      ));
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('ميثاق الأسرة'),
        actions: [
          if (_signed)
            IconButton(
              tooltip: 'شارك أو اطبع',
              icon: const Icon(Icons.ios_share),
              onPressed: () => shareAgreementPng(_boundaryKey, widget.childName),
            ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                if (_error != null) ...[
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                  const SizedBox(height: 12),
                ],
                // An empty bank, said at the top rather than after a button.
                //
                // 1.0.43 hid the signature pad when there were no clauses,
                // which was right on its own and wrong in combination: the
                // explanation only appeared once the save button was pressed,
                // and the save button was inside the block that had just been
                // hidden. The result was a screen with a title and nothing
                // else at all — worse than what it replaced.
                //
                // A clause bank exists for 7-9 only; every other band lands
                // here, and this is the whole content of the screen for them.
                if (!_loading && _pairs.isEmpty) ...[
                  const Text('🕊️', style: TextStyle(fontSize: 44)),
                  const SizedBox(height: 12),
                  const Text(
                    'الميثاق متاح دلوقتي لسنّ ٧–٩ بس.\n\n'
                    'البنود بتتكتب لكل سنّ لوحدها — بند لطفل سبع سنين مش '
                    'نفس البند لابن اتناشر، وميثاق بكلام مش مناسب لسنّه '
                    'بيتوقّع ويتنسي.',
                    textAlign: TextAlign.center,
                    style: TextStyle(height: 1.9),
                  ),
                  const SizedBox(height: 20),
                ],
                if (_pairs.isNotEmpty) ...[
                  const Text(
                    'كل بند على ابنك يقابله بند عليك. ده اللي بيخلّيه ميثاقًا '
                    'مش قائمة أوامر — وابنك هيقيسه عليك في أول يوم.',
                    style: TextStyle(height: 1.7),
                  ),
                  const SizedBox(height: 16),
                ],
                RepaintBoundary(
                  key: _boundaryKey,
                  child: Container(
                    color: Theme.of(context).colorScheme.surface,
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text('ميثاق ${widget.childName}',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                                fontSize: 20, fontWeight: FontWeight.w800)),
                        const SizedBox(height: 12),
                        for (final pair in _pairs)
                          _PairCard(
                            pair: pair,
                            included: !_excluded.contains(pair['key']),
                            onToggle: _signed
                                ? null
                                : (on) => setState(() {
                                      final key = pair['key'] as String;
                                      on ? _excluded.remove(key)
                                         : _excluded.add(key);
                                    }),
                          ),
                        const SizedBox(height: 8),
                        if (_agreement?['signed_by_parent_at'] != null && !_signed)
                          const Text('وقّعتَ — في انتظار توقيع ابنك',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontWeight: FontWeight.w600)),
                        if (_signed)
                          const Text('موقَّع من الطرفين ✍️',
                              textAlign: TextAlign.center,
                              style: TextStyle(fontWeight: FontWeight.w700)),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                if (!_signed && _pairs.isNotEmpty) ...[
                  SignaturePad(
                    key: _signatureKey,
                    label: 'وقّع هنا',
                    onChanged: (has) => setState(() => _hasSignature = has),
                  ),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: _hasSignature ? _saveAndSign : null,
                    child: const Text('احفظ ووقّع'),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'بعد ما توقّع، افتح وضع الطفل عشان ابنك يقرا البنود ويوقّع. '
                    'الميثاق مايشتغلش غير بالتوقيعين.',
                    style: TextStyle(fontSize: 12, height: 1.6),
                  ),
                ],
              ],
            ),
    );
  }
}

class _PairCard extends StatelessWidget {
  const _PairCard({required this.pair, required this.included, this.onToggle});

  final Map<String, dynamic> pair;
  final bool included;
  final ValueChanged<bool>? onToggle;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: included ? 1 : 0.45,
      child: Card(
        margin: const EdgeInsets.symmetric(vertical: 6),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('🧒 '),
                  Expanded(child: Text(pair['child'] as String? ?? '',
                      style: const TextStyle(height: 1.6))),
                  if (onToggle != null)
                    Switch(value: included, onChanged: onToggle),
                ],
              ),
              const Divider(height: 14),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('👤 '),
                  Expanded(child: Text(pair['parent'] as String? ?? '',
                      style: const TextStyle(
                          height: 1.6, fontWeight: FontWeight.w600))),
                ],
              ),
              if (pair['note'] != null) ...[
                const SizedBox(height: 8),
                Text(pair['note'] as String,
                    style: const TextStyle(fontSize: 11, height: 1.5)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
