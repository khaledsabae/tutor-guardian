import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

/// Full-screen, zoomable viewer for a lesson infographic image.
/// Adds a rotate-screen toggle and a download button that stamps the app
/// logo onto the saved copy only (in-app view stays clean).
class InfographicScreen extends StatefulWidget {
  final String url;
  const InfographicScreen({super.key, required this.url});

  @override
  State<InfographicScreen> createState() => _InfographicScreenState();
}

class _InfographicScreenState extends State<InfographicScreen> {
  bool _landscape = false;
  bool _saving = false;

  @override
  void dispose() {
    // Restore the app's portrait-first default on exit.
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
    super.dispose();
  }

  void _toggleRotation() {
    setState(() => _landscape = !_landscape);
    SystemChrome.setPreferredOrientations(
      _landscape
          ? [DeviceOrientation.landscapeLeft, DeviceOrientation.landscapeRight]
          : [DeviceOrientation.portraitUp],
    );
  }

  Future<void> _download() async {
    if (_saving) return;
    setState(() => _saving = true);
    try {
      final bytes = await _buildWatermarked();
      final dir = await getTemporaryDirectory();
      final path =
          '${dir.path}/almorabbi_infographic_${DateTime.now().millisecondsSinceEpoch}.png';
      await File(path).writeAsBytes(bytes);
      await Share.shareXFiles(
        [XFile(path, mimeType: 'image/png')],
        text: 'إنفوجراف من تطبيق المربّي 🌿',
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('تعذّر تحميل الصورة')),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  /// Composites the app logo + brand name onto the infographic (download only).
  Future<Uint8List> _buildWatermarked() async {
    final res = await http.get(Uri.parse(widget.url));
    if (res.statusCode != 200) throw Exception('HTTP ${res.statusCode}');
    final base = await decodeImageFromList(res.bodyBytes);
    final logoData = await rootBundle.load('assets/images/logo.png');
    final logo = await decodeImageFromList(logoData.buffer.asUint8List());

    final w = base.width.toDouble();
    final h = base.height.toDouble();
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    canvas.drawImage(base, Offset.zero, Paint());

    // Small, unobtrusive logo stamp in the bottom-right corner (logo only).
    final logoW = w * 0.06;
    final logoH = logoW * logo.height / logo.width;
    final pad = w * 0.02;
    final left = w - logoW - pad;
    final top = h - logoH - pad;
    canvas.drawImageRect(
      logo,
      Rect.fromLTWH(0, 0, logo.width.toDouble(), logo.height.toDouble()),
      Rect.fromLTWH(left, top, logoW, logoH),
      Paint()..color = const Color(0xF2FFFFFF), // ~95% opacity, no tint
    );

    final picture = recorder.endRecording();
    final img = await picture.toImage(base.width, base.height);
    final png = await img.toByteData(format: ui.ImageByteFormat.png);
    return png!.buffer.asUint8List();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('📊 إنفوجرافيك'),
        actions: [
          IconButton(
            tooltip: 'تدوير الشاشة',
            icon: Icon(_landscape
                ? Icons.stay_current_portrait
                : Icons.screen_rotation),
            onPressed: _toggleRotation,
          ),
          IconButton(
            tooltip: 'تحميل',
            icon: _saving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.download),
            onPressed: _saving ? null : _download,
          ),
        ],
      ),
      backgroundColor: Colors.black,
      body: Center(
        child: InteractiveViewer(
          minScale: 0.8,
          maxScale: 4,
          child: Image.network(
            widget.url,
            fit: BoxFit.contain,
            loadingBuilder: (context, child, progress) => progress == null
                ? child
                : const Center(child: CircularProgressIndicator()),
            errorBuilder: (context, error, stack) => const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'تعذّر تحميل الإنفوجرافيك',
                  style: TextStyle(color: Colors.white70, fontSize: 16),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
