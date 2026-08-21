/// Hijri ⇄ Gregorian converter.
///
/// Local arithmetic, no network, no permission. The disclosure line under the
/// result is part of the feature, not decoration — see `data/hijri_date.dart`
/// for what this conversion can and cannot promise.
library;

import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../../l10n/content_direction.dart';
import '../../../theme/app_theme.dart';
import '../../../theme/design_tokens.dart';
import '../data/hijri_date.dart';

class HijriConverterScreen extends StatefulWidget {
  const HijriConverterScreen({super.key});

  @override
  State<HijriConverterScreen> createState() => _HijriConverterScreenState();
}

class _HijriConverterScreenState extends State<HijriConverterScreen> {
  /// Which way the conversion runs. Starts on Gregorian→Hijri because the
  /// commonest question is "what is today's Hijri date".
  bool _gregorianToHijri = true;

  late DateTime _gregorian;
  late HijriDate _hijri;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _gregorian = DateTime(now.year, now.month, now.day);
    _hijri = gregorianToHijri(_gregorian);
  }

  Future<void> _pickGregorian() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _gregorian,
      firstDate: DateTime(1900),
      lastDate: DateTime(2100),
    );
    if (picked == null) return;
    setState(() {
      _gregorian = DateTime(picked.year, picked.month, picked.day);
      _hijri = gregorianToHijri(_gregorian);
    });
  }

  void _setHijri({int? year, int? month, int? day}) {
    var y = year ?? _hijri.year;
    var m = month ?? _hijri.month;
    var d = day ?? _hijri.day;
    // Changing month or year can strand the day past the end of the new month
    // (30 Dhu al-Hijjah exists only in a leap year). Clamp rather than throw.
    final maxDay = hijriMonthLength(y, m);
    if (d > maxDay) d = maxDay;
    setState(() {
      _hijri = HijriDate(y, m, d);
      _gregorian = hijriToGregorian(y, m, d);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      appBar: AppBar(
        title: Text(l10n.hijriTitle),
        centerTitle: true,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SegmentedButton<bool>(
            segments: [
              ButtonSegment(value: true, label: Text(l10n.hijriToHijri)),
              ButtonSegment(value: false, label: Text(l10n.hijriToGregorian)),
            ],
            selected: {_gregorianToHijri},
            onSelectionChanged: (s) =>
                setState(() => _gregorianToHijri = s.first),
          ),
          const SizedBox(height: 20),
          if (_gregorianToHijri) ..._gregorianInput(l10n) else ..._hijriInput(l10n),
          const SizedBox(height: 24),
          _ResultCard(
            label: _gregorianToHijri ? l10n.hijriResultHijri : l10n.hijriResultGregorian,
            value: _gregorianToHijri
                ? '${arabicDigits(_hijri.day)} ${_hijri.monthName} '
                    '${arabicDigits(_hijri.year)} هـ'
                : '${_gregorian.day}/${_gregorian.month}/${_gregorian.year}',
            arabic: _gregorianToHijri,
          ),
          const SizedBox(height: 16),
          // Not a footnote. The user has to be able to see that this is
          // arithmetic before they plan a fast around it.
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline,
                  size: 16, color: AppTheme.textSecondary),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  l10n.hijriApproximate,
                  style: TextStyle(
                      fontSize: 12.5, color: AppTheme.textSecondary),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  List<Widget> _gregorianInput(AppLocalizations l10n) => [
        OutlinedButton.icon(
          onPressed: _pickGregorian,
          icon: const Icon(Icons.calendar_month_rounded),
          label: Text(
            '${_gregorian.day}/${_gregorian.month}/${_gregorian.year}',
          ),
        ),
      ];

  List<Widget> _hijriInput(AppLocalizations l10n) => [
        ContentDirectionality(
          languageCode: 'ar',
          child: Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<int>(
                  initialValue: _hijri.day,
                  decoration: InputDecoration(labelText: l10n.hijriDay),
                  items: [
                    for (var d = 1;
                        d <= hijriMonthLength(_hijri.year, _hijri.month);
                        d++)
                      DropdownMenuItem(value: d, child: Text(arabicDigits(d))),
                  ],
                  onChanged: (v) => _setHijri(day: v),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                flex: 2,
                child: DropdownButtonFormField<int>(
                  initialValue: _hijri.month,
                  decoration: InputDecoration(labelText: l10n.hijriMonth),
                  items: [
                    for (var m = 1; m <= 12; m++)
                      DropdownMenuItem(
                          value: m, child: Text(hijriMonthNames[m - 1])),
                  ],
                  onChanged: (v) => _setHijri(month: v),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: DropdownButtonFormField<int>(
                  initialValue: _hijri.year,
                  decoration: InputDecoration(labelText: l10n.hijriYear),
                  items: [
                    for (var y = _hijri.year - 60; y <= _hijri.year + 60; y++)
                      DropdownMenuItem(value: y, child: Text(arabicDigits(y))),
                  ],
                  onChanged: (v) => _setHijri(year: v),
                ),
              ),
            ],
          ),
        ),
      ];
}

class _ResultCard extends StatelessWidget {
  final String label;
  final String value;
  final bool arabic;

  const _ResultCard({
    required this.label,
    required this.value,
    required this.arabic,
  });

  @override
  Widget build(BuildContext context) {
    final text = Text(
      value,
      textAlign: TextAlign.center,
      style: TextStyle(
        fontSize: 24,
        fontWeight: FontWeight.w800,
        color: AppTheme.primary,
      ),
    );

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
      decoration: BoxDecoration(
        color: AppTheme.primary.withValues(alpha: .07),
        borderRadius: BorderRadius.circular(Dt.rCard),
      ),
      child: Column(
        children: [
          Text(
            label,
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),
          const SizedBox(height: 8),
          // A Hijri date rendered in Arabic digits and month names is Arabic
          // content; a Gregorian d/m/y is not.
          arabic
              ? ContentDirectionality(languageCode: 'ar', child: text)
              : text,
        ],
      ),
    );
  }
}
