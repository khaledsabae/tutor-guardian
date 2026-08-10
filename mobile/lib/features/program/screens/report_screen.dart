import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:http/http.dart' as http;
import '../../../l10n/app_localizations.dart';

/// Fetches a lesson report (markdown) and renders it.
class ReportScreen extends StatefulWidget {
  final String url;
  const ReportScreen({super.key, required this.url});

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  late Future<String> _content;

  @override
  void initState() {
    super.initState();
    _content = _fetch();
  }

  Future<String> _fetch() async {
    final res = await http.get(Uri.parse(widget.url));
    if (res.statusCode != 200) {
      throw Exception('HTTP ${res.statusCode}');
    }
    return utf8.decode(res.bodyBytes);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(AppLocalizations.of(context).reportScreenTitle)),
      body: FutureBuilder<String>(
        future: _content,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError || (snap.data ?? '').trim().isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(AppLocalizations.of(context).reportLoadError,
                    style: const TextStyle(fontSize: 16)),
              ),
            );
          }
          return Markdown(
            data: snap.data!,
            padding: const EdgeInsets.all(20),
            styleSheet: MarkdownStyleSheet(
              textAlign: WrapAlignment.start,
              h1Align: WrapAlignment.start,
              h2Align: WrapAlignment.start,
            ),
          );
        },
      ),
    );
  }
}
