import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

/// Fetches a lesson data-table (CSV) and renders it as a vertical list of
/// cards (one card per row, "header: value" pairs) — readable on a phone in
/// RTL without horizontal scrolling.
class DataTableScreen extends StatefulWidget {
  final String url;
  const DataTableScreen({super.key, required this.url});

  @override
  State<DataTableScreen> createState() => _DataTableScreenState();
}

class _DataTableScreenState extends State<DataTableScreen> {
  late Future<List<List<String>>> _rows;

  @override
  void initState() {
    super.initState();
    _rows = _fetch();
  }

  Future<List<List<String>>> _fetch() async {
    final res = await http.get(Uri.parse(widget.url));
    if (res.statusCode != 200) {
      throw Exception('HTTP ${res.statusCode}');
    }
    return _parseCsv(utf8.decode(res.bodyBytes));
  }

  /// Minimal quote-aware CSV parser (handles commas/newlines inside quotes
  /// and "" escapes).
  List<List<String>> _parseCsv(String text) {
    final rows = <List<String>>[];
    var field = StringBuffer();
    var row = <String>[];
    var inQuotes = false;
    for (var i = 0; i < text.length; i++) {
      final c = text[i];
      if (inQuotes) {
        if (c == '"') {
          if (i + 1 < text.length && text[i + 1] == '"') {
            field.write('"');
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          field.write(c);
        }
      } else if (c == '"') {
        inQuotes = true;
      } else if (c == ',') {
        row.add(field.toString().trim());
        field = StringBuffer();
      } else if (c == '\n' || c == '\r') {
        if (c == '\r' && i + 1 < text.length && text[i + 1] == '\n') i++;
        row.add(field.toString().trim());
        field = StringBuffer();
        if (row.any((f) => f.isNotEmpty)) rows.add(row);
        row = <String>[];
      } else {
        field.write(c);
      }
    }
    if (field.isNotEmpty || row.isNotEmpty) {
      row.add(field.toString().trim());
      if (row.any((f) => f.isNotEmpty)) rows.add(row);
    }
    return rows;
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: const Text('📋 جدول البيانات')),
      body: FutureBuilder<List<List<String>>>(
        future: _rows,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final data = snap.data ?? const [];
          if (snap.hasError || data.length < 2) {
            return const Center(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text('تعذّر تحميل الجدول', style: TextStyle(fontSize: 16)),
              ),
            );
          }
          final header = data.first;
          final body = data.skip(1).toList();
          return ListView.builder(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
            itemCount: body.length,
            itemBuilder: (context, index) {
              final r = body[index];
              return Card(
                margin: const EdgeInsets.only(bottom: 12),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // First column acts as the card title.
                      if (r.isNotEmpty && r[0].isNotEmpty) ...[
                        Text(
                          r[0],
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                            color: scheme.primary,
                          ),
                        ),
                        const Divider(height: 18),
                      ],
                      for (var i = 1; i < header.length; i++)
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                flex: 2,
                                child: Text(
                                  header[i],
                                  style: TextStyle(
                                    fontWeight: FontWeight.w600,
                                    color: scheme.onSurfaceVariant,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                flex: 3,
                                child: Text(i < r.length ? r[i] : ''),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
