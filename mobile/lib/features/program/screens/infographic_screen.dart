import 'package:flutter/material.dart';

/// Full-screen, zoomable viewer for a lesson infographic image.
class InfographicScreen extends StatelessWidget {
  final String url;
  const InfographicScreen({super.key, required this.url});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('📊 إنفوجرافيك')),
      backgroundColor: Colors.black,
      body: Center(
        child: InteractiveViewer(
          minScale: 0.8,
          maxScale: 4,
          child: Image.network(
            url,
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
