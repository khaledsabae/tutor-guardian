/// Deep link handler — Phase 0/1.
///
/// Wires app_links to route incoming https://tg-api.alsaba.cloud/{go,l,p}
/// links into the app. The navigatorKey is required because the first link
/// may arrive before MaterialApp is fully built.
library;

import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';

import '../../api/tg_client.dart';
import '../../core/app_routes.dart';
import '../../features/referral/referral_service.dart';

class DeepLinkHandler {
  DeepLinkHandler._();
  static final DeepLinkHandler instance = DeepLinkHandler._();

  AppLinks? _appLinks;
  GlobalKey<NavigatorState>? _navigatorKey;

  Future<void> init(GlobalKey<NavigatorState> navigatorKey) async {
    _navigatorKey = navigatorKey;
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

  /// Public dispatch entry used by push taps and other non-app-links
  /// entry points. No-op if the navigator key is not ready.
  Future<void> dispatch(String link) async {
    final key = _navigatorKey;
    if (key == null) return;
    try {
      final uri = Uri.parse(link);
      _handle(uri, key);
    } catch (_) {
      // ignore malformed links
    }
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
      // The root route is already a RootScaffold built by _AppBootstrapper.
      // Pushing another one would bypass the onboarding / child-mode /
      // force-update gates and reset every tab's state, so just unwind back
      // to it.
      navigator.popUntil((route) => route.isFirst);
      return;
    }

    // Feedback reply: /inbox — sent as `data.link` on the push that fires when
    // Khaled answers a piece of feedback. The replies render at the top of the
    // feedback screen, so that is where the notification lands.
    if (path == '/inbox') {
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.feedback());
      return;
    }

    // Lesson deep link: /l/{lesson_id}
    final lessonMatch = RegExp(r'^/l/([^/]+)$').firstMatch(path);
    if (lessonMatch != null) {
      final lessonId = lessonMatch.group(1)!;
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.lesson(lessonId, '0-1'));
      return;
    }

    // Path deep link: /p/{path_id}
    final pathMatch = RegExp(r'^/p/([^/]+)$').firstMatch(path);
    if (pathMatch != null) {
      final pathId = pathMatch.group(1)!;
      // Default age group; the screen can adapt if not found.
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.pathDetail(pathId, '0-1'));
      return;
    }
  }
}
