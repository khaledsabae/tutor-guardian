/// Deep link handler — Phase 0/1.
///
/// Wires app_links to route incoming https://tg-api.alsaba.cloud/{go,l,p}
/// links into the app. The navigatorKey is required because the first link
/// may arrive before MaterialApp is fully built.
library;

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';

import '../../api/tg_client.dart';
import '../../features/program/screens/lesson_screen.dart';
import '../../features/program/screens/path_detail_screen.dart';
import '../../features/referral/referral_service.dart';
import '../../main.dart';

class DeepLinkHandler {
  DeepLinkHandler._();
  static final DeepLinkHandler instance = DeepLinkHandler._();

  AppLinks? _appLinks;

  Future<void> init(GlobalKey<NavigatorState> navigatorKey) async {
    _appLinks = AppLinks();

    // Handle the link that launched the app (cold start).
    try {
      final initial = await _appLinks!.getInitialLink();
      if (initial != null) {
        _handle(initial, navigatorKey);
      }
    } catch (_) {
      // ignore
    }

    // Handle links while the app is running (warm start).
    _appLinks!.uriLinkStream.listen(
      (uri) => _handle(uri, navigatorKey),
      onError: (_) { /* ignore */ },
    );
  }

  void _handle(Uri uri, GlobalKey<NavigatorState> key) {
    final path = uri.path;
    final context = key.currentContext;
    if (context == null) return;

    final navigator = Navigator.of(context);

    // Referral landing: /go?ref=XXXX → save code + home.
    if (path == '/go' || path.startsWith('/go/')) {
      final code = uri.queryParameters['ref'] ?? '';
      if (code.isNotEmpty) {
        unawaited(TgClient().ensureSession().then((_) async {
          await ReferralService.instance.claimManual(code);
        }));
      }
      navigator.pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const RootScaffold()),
        (route) => false,
      );
      return;
    }

    // Lesson deep link: /l/{lesson_id}
    final lessonMatch = RegExp(r'^/l/([^/]+)$').firstMatch(path);
    if (lessonMatch != null) {
      final lessonId = lessonMatch.group(1)!;
      navigator.push(
        MaterialPageRoute(builder: (_) => LessonScreen(lessonId: lessonId, ageGroup: '0-1')),
      );
      return;
    }

    // Path deep link: /p/{path_id}
    final pathMatch = RegExp(r'^/p/([^/]+)$').firstMatch(path);
    if (pathMatch != null) {
      final pathId = pathMatch.group(1)!;
      // Default age group; the screen can adapt if not found.
      navigator.push(
        MaterialPageRoute(
          builder: (_) => PathDetailScreen(pathId: pathId, ageGroup: '0-1'),
        ),
      );
      return;
    }
  }
}

// Best-effort wrapper so we never have to import dart:async just for this.
void unawaited(Future<void> future) {}
