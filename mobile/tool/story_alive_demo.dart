/// A preview build of the story reader alone, every bundled story — to see
/// the «صورة حيّة» sample (maryam_toys told with its original painted pages,
/// the camera following the narrator) on an emulator or a phone without
/// onboarding a child, and so without writing anything to the production
/// backend. The narration it plays is the live recordings' static files
/// (read only).
///
///   flutter build apk --debug -t tool/story_alive_demo.dart \
///     --dart-define=API_BASE_URL=https://tg-api.alsaba.cloud
///
/// Not the app: no Firebase, no accounts, no analytics. Never shipped.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:almorabbi/features/program/data/story_models.dart';
import 'package:almorabbi/features/program/screens/story_reader_screen.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/l10n/l10n_global.dart';
import 'package:almorabbi/theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: _Demo()));
}

class _Demo extends StatefulWidget {
  const _Demo();

  @override
  State<_Demo> createState() => _DemoState();
}

class _DemoState extends State<_Demo> {
  Locale _locale = const Locale('ar');

  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    theme: AppTheme.light(),
    locale: _locale,
    supportedLocales: AppLocalizations.supportedLocales,
    localizationsDelegates: const [
      AppLocalizations.delegate,
      GlobalMaterialLocalizations.delegate,
      GlobalWidgetsLocalizations.delegate,
      GlobalCupertinoLocalizations.delegate,
    ],
    builder: (context, child) {
      AppL10n.current = AppLocalizations.of(context);
      return child!;
    },
    home: _Picker(
      language: _locale.languageCode,
      onLanguage: (l) => setState(() => _locale = Locale(l)),
    ),
  );
}

class _Picker extends StatelessWidget {
  const _Picker({required this.language, required this.onLanguage});

  final String language;
  final ValueChanged<String> onLanguage;

  Future<List<Story>> _load() async {
    final file = language == 'en'
        ? 'assets/data/stories_en.json'
        : 'assets/data/stories.json';
    final list = jsonDecode(await rootBundle.loadString(file)) as List;
    final stories = [
      for (final j in list) Story.fromJson(j as Map<String, dynamic>),
    ];
    return stories;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Story preview'),
      actions: [
        TextButton(
          key: const ValueKey('lang'),
          onPressed: () => onLanguage(language == 'ar' ? 'en' : 'ar'),
          child: Text(language == 'ar' ? 'EN' : 'AR'),
        ),
      ],
    ),
    body: FutureBuilder<List<Story>>(
      key: ValueKey(language),
      future: _load(),
      builder: (context, snap) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final s in snap.data ?? const <Story>[])
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: FilledButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => StoryReaderScreen(story: s),
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(2),
                  child: Text(s.title, style: const TextStyle(fontSize: 14)),
                ),
              ),
            ),
        ],
      ),
    ),
  );
}
