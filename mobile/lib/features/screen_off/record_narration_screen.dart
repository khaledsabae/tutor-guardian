/// Recording a story in a parent's voice.
///
/// One take, kept on the phone. The screen shows the story text large enough
/// to read aloud from, a record button, and a way to listen back — nothing
/// resembling an editor, because a parent who feels they are producing
/// something will do it once and never again, and the version their child
/// wants is the imperfect one.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:record/record.dart';

import 'narration_store.dart';
import 'audio_tag.dart';

class RecordNarrationScreen extends StatefulWidget {
  const RecordNarrationScreen({
    super.key,
    required this.storyKey,
    required this.storyText,
    this.title = 'سجّل بصوتك',
  });

  final String storyKey;
  final String storyText;
  final String title;

  @override
  State<RecordNarrationScreen> createState() => _RecordNarrationScreenState();
}

class _RecordNarrationScreenState extends State<RecordNarrationScreen> {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  bool _recording = false;
  bool _hasTake = false;
  String? _path;
  String? _error;
  Duration _elapsed = Duration.zero;
  Timer? _ticker;

  @override
  void initState() {
    super.initState();
    _loadExisting();
  }

  Future<void> _loadExisting() async {
    final existing = await NarrationStore.instance.find(widget.storyKey);
    if (existing != null && mounted) {
      setState(() { _path = existing.path; _hasTake = true; });
    }
  }

  Future<void> _start() async {
    if (!await _recorder.hasPermission()) {
      setState(() => _error = 'التسجيل محتاج إذن الميكروفون.');
      return;
    }
    final path = await NarrationStore.instance.pathFor(widget.storyKey);
    await _recorder.start(const RecordConfig(), path: path);
    setState(() {
      _recording = true;
      _hasTake = false;
      _path = path;
      _elapsed = Duration.zero;
      _error = null;
    });
    _ticker = Timer.periodic(const Duration(seconds: 1),
        (_) => setState(() => _elapsed += const Duration(seconds: 1)));
  }

  Future<void> _stop() async {
    _ticker?.cancel();
    final path = await _recorder.stop();
    if (path != null) {
      await NarrationStore.instance.register(widget.storyKey, path);
    }
    if (mounted) setState(() { _recording = false; _hasTake = path != null; });
  }

  Future<void> _preview() async {
    if (_path == null) return;
    await _player.setAudioSource(AudioSource.file(
      _path!,
      tag: audioTag(id: _path!, title: 'معاينة التسجيل'),
    ));
    await _player.play();
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }

  String get _clock =>
      '${_elapsed.inMinutes.toString().padLeft(2, '0')}:'
      '${(_elapsed.inSeconds % 60).toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'اقرا القصة بصوتك مرة واحدة. ابنك هيسمعها بصوتك في أي وقت — '
            'حتى وإنت مش موجود. التسجيل بيفضل على الجهاز ومابيتبعتش لأي حتة.',
            style: TextStyle(height: 1.8),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(widget.storyText,
                style: const TextStyle(fontSize: 17, height: 2.0)),
          ),
          const SizedBox(height: 24),
          if (_error != null) ...[
            Text(_error!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 12),
          ],
          Center(
            child: Text(_recording ? _clock : (_hasTake ? 'التسجيل جاهز ✓' : ''),
                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: _recording ? _stop : _start,
            icon: Icon(_recording ? Icons.stop : Icons.mic),
            label: Text(_recording ? 'خلّصت' : (_hasTake ? 'سجّل تاني' : 'ابدأ التسجيل')),
          ),
          if (_hasTake && !_recording) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _preview,
              icon: const Icon(Icons.play_arrow),
              label: const Text('اسمع'),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () async {
                await NarrationStore.instance.delete(widget.storyKey);
                if (context.mounted) Navigator.of(context).pop(false);
              },
              child: const Text('احذف التسجيل'),
            ),
          ],
          const SizedBox(height: 16),
          if (_hasTake && !_recording)
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('تمام، خلصنا'),
            ),
        ],
      ),
    );
  }
}
