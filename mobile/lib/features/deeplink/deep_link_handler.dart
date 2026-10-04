/// Deep link handler — Phase 0/1.
///
/// Wires app_links to route incoming https://tg-api.alsaba.cloud/{go,l,p}
/// links into the app. The navigatorKey is required because the first link
/// may arrive before MaterialApp is fully built.
library;

import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/tg_client.dart';
import '../../core/app_routes.dart';
import '../../features/referral/referral_service.dart';
import '../routine/providers/child_mode_providers.dart';

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

  /// [_handle] for tests, which cannot drive app_links or FCM.
  @visibleForTesting
  void handleForTest(Uri uri, GlobalKey<NavigatorState> key) => _handle(uri, key);

  /// True while a child is holding the phone — a parent's screen must not be
  /// pushed over the child surface.
  bool _childModeActive(BuildContext context) {
    try {
      return ProviderScope.containerOf(context, listen: false)
          .read(childModeProvider)
          .active;
    } catch (_) {
      return false; // no scope (tests, very early start): nothing to protect
    }
  }

  /// The last parent link child mode held back, and the watch that replays it.
  Uri? _held;
  ProviderSubscription<bool>? _heldWatch;

  /// Keeps [uri] — the latest one wins — and opens it as soon as child mode
  /// ends. That also covers a cold start: `restore()` reports child mode as
  /// active while it checks the network, and a push tapped to launch the app
  /// arrives in exactly that window; it used to be dropped.
  void _holdUntilChildModeEnds(
      BuildContext context, Uri uri, GlobalKey<NavigatorState> key) {
    _held = uri;
    if (_heldWatch != null) return;
    try {
      final container = ProviderScope.containerOf(context, listen: false);
      _heldWatch = container.listen<bool>(
        childModeProvider.select((s) => s.active),
        (_, active) {
          if (active) return;
          _heldWatch?.close();
          _heldWatch = null;
          final link = _held;
          _held = null;
          if (link == null) return;
          // After the frame that swaps the child surface for the parent app.
          WidgetsBinding.instance.addPostFrameCallback((_) => _handle(link, key));
        },
      );
    } catch (_) {
      _held = null; // no scope to watch: nothing to replay into
    }
  }

  void _handle(Uri uri, GlobalKey<NavigatorState> key) {
    final path = uri.path;
    final context = key.currentContext;
    if (context == null) return;
    final childMode = _childModeActive(context);

    // Referral landing: /go?ref=XXXX → save code + home. The code is saved
    // whatever is on screen — it is the install's attribution, not a parent
    // screen; only the unwinding waits for the parent app.
    if (path == '/go' || path.startsWith('/go/')) {
      final code = uri.queryParameters['ref'] ?? '';
      if (code.isNotEmpty) {
        unawaited(TgClient.shared.ensureSession().then((_) async {
          await ReferralService.instance.claimManual(code);
        }));
      }
      // The root route is already a RootScaffold built by _AppBootstrapper.
      // Pushing another one would bypass the onboarding / child-mode /
      // force-update gates and reset every tab's state, so just unwind back
      // to it.
      if (!childMode) Navigator.of(context).popUntil((route) => route.isFirst);
      return;
    }

    // While a child holds the phone, no other link opens anything: every one
    // below is the parent's. /missions would put the evening confirmation —
    // the parent's own session — over the child surface, where a child could
    // confirm their own claims; /license, /inbox, a lesson, a milestone are
    // parent screens too. The link is kept and opens when child mode ends.
    if (childMode) {
      _holdUntilChildModeEnds(context, uri, key);
      return;
    }

    final navigator = Navigator.of(context);

    // Feedback reply: /inbox — sent as `data.link` on the push that fires when
    // Khaled answers a piece of feedback. The replies render at the top of the
    // feedback screen, so that is where the notification lands.
    if (path == '/inbox') {
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.feedback());
      return;
    }

    // Evening mission digest: /missions — the one notification this feature
    // sends, and it is addressed to the parent. Without this arm the digest
    // opened the app at home and the parent had to go find the screen, which
    // is most of the way back to not being told at all.
    if (path == '/missions') {
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.pendingMissions());
      return;
    }

    // Internet-licence safety alert: /license. The one immediate push this
    // product sends, and it is addressed to the parent. It must land on the
    // talking point, not on the home screen.
    if (path == '/license') {
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.parentLicense());
      return;
    }

    // Milestone push: /milestones/{child_id}/{milestone_key} (MOBILE_API
    // §11.5.3) — "turning seven next month". Opens that child's card; the
    // screen falls back to the child's list when the card is not theirs.
    // Parent-only content (the child-mode guard above covers it).
    final milestoneMatch =
        RegExp(r'^/milestones/(\d+)/([A-Za-z0-9_\-]+)/?$').firstMatch(path);
    if (milestoneMatch != null) {
      final childId = int.parse(milestoneMatch.group(1)!);
      final key = milestoneMatch.group(2)!;
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.milestoneDetail(childId, key));
      return;
    }

    // Lesson deep link: /l/{lesson_id}
    final lessonMatch = RegExp(r'^/l/([^/]+)$').firstMatch(path);
    if (lessonMatch != null) {
      final lessonId = lessonMatch.group(1)!;
      navigator.popUntil((route) => route.isFirst);
      // Empty age band, not a made-up one. '0-1' is not a valid group at all
      // — the backend accepts prenatal-1, 0-3, 2-3, 4-6, 7-9, 10-12, 13-15,
      // 16-18 — so every deep-linked lesson showed a fabricated age chip.
      // Empty makes the screen fall back to the active child's own band.
      navigator.push(AppRoutes.lesson(lessonId, ''));
      return;
    }

    // Path deep link: /p/{path_id}
    final pathMatch = RegExp(r'^/p/([^/]+)$').firstMatch(path);
    if (pathMatch != null) {
      final pathId = pathMatch.group(1)!;
      navigator.popUntil((route) => route.isFirst);
      navigator.push(AppRoutes.pathDetail(pathId, ''));
      return;
    }
  }
}
