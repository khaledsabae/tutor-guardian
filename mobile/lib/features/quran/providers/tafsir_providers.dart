/// Tafsir of an ayah, fetched from the backend that already had it.
///
/// `/api/tafsir/{surah}/{ayah}` has proxied `mcp.tafsir.net` with a 30-day
/// cache since long before this file existed, and `grep -r tafsir mobile/lib`
/// returned nothing: the most expensive thing in the Quran feature was built,
/// paid for, and invisible.
///
/// Two rules this file exists to keep:
///
///  * **Attribution is not decoration.** Every entry carries the name of the
///    mufassir and his death year, and the UI renders it. A tafsir with the
///    attribution stripped is an anonymous claim about the meaning of the
///    Qur'an, which is exactly what the content guards in `ops/tools/` exist
///    to prevent elsewhere in this repo.
///  * **No documented sabab nuzool is an answer.** The backend 404s with a
///    sentence saying so; that is content, not an error, and `getNuzool`
///    already turns it into `null` rather than a throw.
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../state/chat_notifier.dart' show tgClientProvider;
import '../../program/providers/lesson_assets_provider.dart'
    show contentLanguageProvider;

/// Tafsir sources to request for a given app language.
///
/// The backend serves 28 sources, 22 of them Arabic, and a request that names
/// none gets the Arabic default. That is what shipped first, so an English
/// parent long-pressed an ayah and got a wall of Arabic — the same shape of
/// bug as the curriculum text that stayed Arabic until the client started
/// sending `lang`.
///
/// `mukhtasar_en` is the English choice because it is the only English source
/// with full coverage; `jalalayn_en` is marked sparse and would leave holes.
/// Nothing is listed for other languages: the app ships Arabic and English
/// interface only, and there is no French tafsir in the catalogue to reach for
/// even when one is added.
///
/// This is tafsir — an explanation of the meaning — never a translation of the
/// Qur'an itself. The attribution rendered above every block says which
/// commentary it is, which is exactly the distinction the content guards in
/// `ops/tools/check_quran_rendering.py` exist to protect.
List<String>? tafsirSourcesFor(String language) =>
    switch (language) { 'en' => const ['mukhtasar_en'], _ => null };

/// The language a source slug is written in, read off the slug.
///
/// The backend's per-entry payload carries no language field, and the sheet
/// needs one to decide text direction. The catalogue's own convention is a
/// language suffix on non-Arabic slugs (`mukhtasar_en`, `saadi_ru`,
/// `zakaria_bn`); anything without one is Arabic. A slug that breaks the
/// convention falls through to counting the characters, which is why the sheet
/// passes both signals rather than trusting this alone.
String? languageOfSource(String slug) {
  for (final code in const ['en', 'bn', 'ru', 'fr', 'tr', 'ur', 'id']) {
    if (slug.endsWith('_$code')) return code;
  }
  return slug.isEmpty ? null : 'ar';
}

/// One mufassir's word on one ayah.
class TafsirEntry {
  /// Slug of the source (`saadi`, `tabary`, …) — stable, not for display.
  final String source;

  /// Language the [text] is written in, derived from [source].
  ///
  /// Drives text direction in the sheet. `null` when the slug says nothing,
  /// which leaves the decision to the characters themselves.
  String? get language => languageOfSource(source);

  /// Display name of the tafsir and its author. Never rendered as optional.
  final String attribution;

  final String text;

  /// Served from the backend's 30-day cache rather than fetched upstream.
  final bool cached;

  const TafsirEntry({
    required this.source,
    required this.attribution,
    required this.text,
    this.cached = false,
  });

  /// Builds an entry from one element of `TafsirResponse.results`.
  ///
  /// Returns `null` for an entry the backend marked failed or left empty —
  /// `results` carries one element per requested source and a source that did
  /// not answer arrives with `error` set. Showing that row would be showing a
  /// parent an error where a tafsir should be.
  static TafsirEntry? fromJson(Map<String, dynamic> j) {
    final text = (j['text'] as String?)?.trim() ?? '';
    final attribution = (j['attribution'] as String?)?.trim() ?? '';
    final error = (j['error'] as String?)?.trim() ?? '';
    if (text.isEmpty || attribution.isEmpty || error.isNotEmpty) return null;
    return TafsirEntry(
      source: (j['source'] as String?) ?? '',
      attribution: attribution,
      text: text,
      cached: j['cached'] == true,
    );
  }
}

/// Everything the tafsir sheet shows for one ayah.
class AyahExplanation {
  final int surah;
  final int ayah;

  /// Successful tafsir entries, in the order the backend returned them.
  final List<TafsirEntry> entries;

  /// The backend's pre-formatted blob. Kept as the fallback for the case where
  /// every structured entry was dropped but the server still had something to
  /// say (its own `FALLBACK_MESSAGE` included).
  final String formatted;

  /// Reason for revelation, or `null` when none is documented — the common case.
  final String? nuzool;

  /// Attribution for [nuzool]. Present whenever [nuzool] is.
  final String? nuzoolAttribution;

  const AyahExplanation({
    required this.surah,
    required this.ayah,
    required this.entries,
    required this.formatted,
    this.nuzool,
    this.nuzoolAttribution,
  });

  /// True when there is no structured tafsir to render and the caller should
  /// fall back to [formatted].
  bool get isEmpty => entries.isEmpty;
}

List<TafsirEntry> _entriesOf(Map<String, dynamic> tafsir) =>
    (tafsir['results'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map(TafsirEntry.fromJson)
        .whereType<TafsirEntry>()
        .toList(growable: false);

/// Tafsir + sabab nuzool for one ayah.
///
/// `autoDispose` because a reader moves through hundreds of ayahs in a sitting
/// and each result is a few kilobytes of Arabic prose; the backend cache, not
/// this provider, is what makes a re-open cheap.
final ayahExplanationProvider =
    FutureProvider.autoDispose.family<AyahExplanation, (int, int)>(
  (ref, key) async {
    final (surah, ayah) = key;
    final client = ref.read(tgClientProvider);
    final sources = tafsirSourcesFor(ref.watch(contentLanguageProvider));

    // Two independent calls; a dead nuzool lookup must not cost the tafsir.
    final tafsirFuture = client.getTafsir(surah, ayah, sources: sources);
    final nuzoolFuture = client.getNuzool(surah, ayah).catchError(
          (_) => null,
        );

    var tafsir = await tafsirFuture;
    final nuzool = await nuzoolFuture;

    var entries = _entriesOf(tafsir);

    // An ayah the English commentary does not cover would otherwise show the
    // reader nothing at all. Arabic they cannot read beats an empty sheet, and
    // the attribution on it still says which commentary they are looking at.
    if (entries.isEmpty && sources != null) {
      tafsir = await client.getTafsir(surah, ayah);
      entries = _entriesOf(tafsir);
    }

    final nuzoolText = (nuzool?['text'] as String?)?.trim();
    final nuzoolAttr = (nuzool?['attribution'] as String?)?.trim();

    return AyahExplanation(
      surah: surah,
      ayah: ayah,
      entries: entries,
      formatted: (tafsir['formatted'] as String?)?.trim() ?? '',
      // Same rule as the tafsir entries: unattributed text about revelation is
      // not shown at all.
      nuzool: (nuzoolText != null &&
              nuzoolText.isNotEmpty &&
              nuzoolAttr != null &&
              nuzoolAttr.isNotEmpty)
          ? nuzoolText
          : null,
      nuzoolAttribution: (nuzoolText != null && nuzoolText.isNotEmpty)
          ? nuzoolAttr
          : null,
    );
  },
);
