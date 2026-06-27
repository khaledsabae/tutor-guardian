/// In-app feedback — the parent sends Khaled a written note and/or a voice
/// note. Posts to `/api/feedback/app` (public). Voice is optional and degrades
/// gracefully if the mic permission is denied.
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

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
  final _rec = AudioRecorder();

  bool _recording = false;
  String? _audioPath;
  bool _sending = false;

  @override
  void dispose() {
    _message.dispose();
    _contact.dispose();
    _rec.dispose();
    super.dispose();
  }

  Future<void> _toggleRecord() async {
    try {
      if (_recording) {
        final path = await _rec.stop();
        setState(() {
          _recording = false;
          _audioPath = path;
        });
        return;
      }
      if (!await _rec.hasPermission()) {
        _snack('يلزم إذن الميكروفون لتسجيل ملاحظة صوتية.');
        return;
      }
      // App's private docs dir — always writable (the cache/temp dir can be
      // read-only on some devices, which surfaced as "errno = 30").
      final dir = await getApplicationDocumentsDirectory();
      await dir.create(recursive: true);
      final path =
          '${dir.path}/feedback_${DateTime.now().millisecondsSinceEpoch}.m4a';
      await _rec.start(const RecordConfig(encoder: AudioEncoder.aacLc),
          path: path);
      setState(() => _recording = true);
    } catch (e) {
      setState(() => _recording = false);
      _snack('تعذّر التسجيل الصوتي على هذا الجهاز — يمكنك الكتابة بدلاً منه.');
    }
  }

  Future<void> _send() async {
    final msg = _message.text.trim();
    if (msg.isEmpty && _audioPath == null) {
      _snack('اكتب ملاحظتك أو سجّل رسالة صوتية أولاً.');
      return;
    }
    setState(() => _sending = true);
    try {
      String? audioB64;
      if (_audioPath != null) {
        final bytes = await File(_audioPath!).readAsBytes();
        if (bytes.length > 2 * 1024 * 1024) {
          _snack('الملف الصوتي كبير جدًا (أكبر من 2 ميجا). جرّب تسجيل أقصر.');
          setState(() => _sending = false);
          return;
        }
        audioB64 = base64Encode(bytes);
      }
      final id = await ref.read(tgClientProvider).sendAppFeedback(
            message: msg,
            contact: _contact.text.trim(),
            audioBase64: audioB64,
          );
      if (!mounted) return;
      _snack('وصلت ملاحظتك، شكراً لك! 🌿 (ID: ${id.substring(0, 8)})', ok: true);
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
            'رأيك يهمنا ويصل مباشرةً لفريق المربي الذكي. اكتب ملاحظتك أو سجّلها صوتياً.',
            style: TextStyle(fontSize: 15, height: 1.5),
          ),
          const SizedBox(height: 20),
          TextField(
            controller: _message,
            maxLines: 6,
            maxLength: 1000,
            textInputAction: TextInputAction.newline,
            decoration: const InputDecoration(
              labelText: 'ملاحظتك',
              hintText: 'اكتب اقتراحك أو المشكلة التي واجهتك…',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surfaceAlt,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              children: [
                IconButton.filled(
                  onPressed: _sending ? null : _toggleRecord,
                  icon: Icon(_recording ? Icons.stop : Icons.mic),
                  style: IconButton.styleFrom(
                    backgroundColor:
                        _recording ? AppTheme.dangerFg : AppTheme.primary,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    _recording
                        ? 'جارٍ التسجيل… اضغط للإيقاف'
                        : _audioPath != null
                            ? 'تم تسجيل ملاحظة صوتية ✓'
                            : 'سجّل ملاحظة صوتية (اختياري)',
                    style: const TextStyle(fontSize: 14),
                  ),
                ),
                if (_audioPath != null && !_recording)
                  IconButton(
                    onPressed: () => setState(() => _audioPath = null),
                    icon: const Icon(Icons.delete_outline),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
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
