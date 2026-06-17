import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

/// Fetches a lesson data-table (CSV) and renders it as a scrollable table.
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
  /// and "" escapes). Adequate for the generated lesson data tables.
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
        row.add(field.toString());
        field = StringBuffer();
      } else if (c == '\n' || c == '\r') {
        if (c == '\r' && i + 1 < text.length && text[i + 1] == '\n') i++;
        row.add(field.toString());
        field = StringBuffer();
        if (row.any((f) => f.trim().isNotEmpty)) rows.add(row);
        row = <String>[];
      } else {
        field.write(c);
      }
    }
    if (field.isNotEmpty || row.isNotEmpty) {
      row.add(field.toString());
      if (row.any((f) => f.trim().isNotEmpty)) rows.add(row);
    }
    return rows;
  }

  @override
  Widget build(BuildContext context) {
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
          return SingleChildScrollView(
            scrollDirection: Axis.vertical,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                columns: [
                  for (final h in header)
                    DataColumn(
                      label: Text(h,
                          style: const TextStyle(fontWeight: FontWeight.bold)),
                    ),
                ],
                rows: [
                  for (final r in body)
                    DataRow(
                      cells: [
                        for (var i = 0; i < header.length; i++)
                          DataCell(Text(i < r.length ? r[i] : '')),
                      ],
                    ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
