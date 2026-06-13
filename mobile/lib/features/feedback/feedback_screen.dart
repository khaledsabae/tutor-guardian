/// In-app feedback — the parent sends Khaled a written note. Posts to
/// `/api/feedback/app` (public). (Voice notes are a planned follow-up; the
/// backend already accepts an optional base64 audio field.)
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/chat_notifier.dart' show tgClientProvider;
import '../../theme/app_theme.dart';
import '../../widgets/ui/bouncy_button.dart';

class FeedbackScreen extends ConsumerStatefulWidget {
  const FeedbackScreen({super.key});

  @override
  ConsumerState<FeedbackScreen> createState() => _FeedbackScreenState();
}

class _FeedbackScreenState extends ConsumerState<FeedbackScreen> {
  final _message = TextEditingController();
  final _contact = TextEditingController();
  bool _sending = false;

  @override
  void dispose() {
    _message.dispose();
    _contact.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final msg = _message.text.trim();
    if (msg.isEmpty) {
      _snack('اكتب ملاحظتك أولاً.');
      return;
    }
    setState(() => _sending = true);
    try {
      await ref.read(tgClientProvider).sendAppFeedback(
            message: msg,
            contact: _contact.text.trim(),
          );
      if (!mounted) return;
      _snack('وصلت ملاحظتك، شكراً لك! 🌿', ok: true);
      Navigator.of(context).pop();
    } catch (e) {
      _snack('تعذّر الإرسال: $e');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  void _snack(String text, {bool ok = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(text),
      backgroundColor: ok ? AppTheme.success : AppTheme.dangerFg,
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('شاركنا رأيك')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text(
            'رأيك يهمنا ويصل مباشرةً لفريق المربي الذكي. اكتب اقتراحك أو المشكلة التي واجهتك.',
            style: TextStyle(fontSize: 15, height: 1.5),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _message,
            maxLines: 7,
            maxLength: 1000,
            textInputAction: TextInputAction.newline,
            decoration: const InputDecoration(
              labelText: 'ملاحظتك',
              hintText: 'اكتب هنا…',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _contact,
            decoration: const InputDecoration(
              labelText: 'وسيلة تواصل (اختياري)',
              hintText: 'بريد أو رقم للرد عليك',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 24),
          BouncyButton(
            label: _sending ? 'جارٍ الإرسال…' : 'إرسال',
            icon: const Icon(Icons.send, color: Colors.white),
            onTap: _sending ? null : _send,
          ),
        ],
      ),
    );
  }
}
