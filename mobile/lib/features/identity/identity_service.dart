/// Identity service — Phase 1.2 optional Google Sign-In.
///
/// Links a Google account to the anonymous device_id on the backend so
/// child data and referral attribution survive app reinstall. The flow is
/// opt-in only; the user can keep using the app anonymously.
library;

import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../api/tg_client.dart';
import '../../core/analytics.dart';

class IdentityService {
  IdentityService._();
  static final IdentityService instance = IdentityService._();

  static const _kLinked = 'identity.linked';

  // Web client ID from Google Cloud Console → OAuth client ID → Web application.
  // Used by the google_sign_in plugin on Android to request an id_token.
  static const String _serverClientId = String.fromEnvironment(
    'GOOGLE_SERVER_CLIENT_ID',
    defaultValue: '620240456244-e0ap0isfsufoue1atumhen5l0ttlm6ga.apps.googleusercontent.com',
  );

  final GoogleSignIn _googleSignIn = GoogleSignIn(
    scopes: ['email', 'profile'],
    serverClientId: _serverClientId.isEmpty ? null : _serverClientId,
  );

  /// Returns true if a previous sign-in happened on this device.
  Future<bool> get isLinked async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_kLinked) ?? false;
  }

  /// Best-effort restore on cold start. If the user previously signed in, we
  /// re-auth silently and tell the backend to link this device_id.
  Future<void> silentRestore() async {
    if (!await isLinked) return;
    if (_serverClientId.isEmpty) return;
    try {
      final account = await _googleSignIn.signInSilently();
      if (account == null) return;
      await _link(account);
    } catch (_) {
      // ignore — user will see the opt-in button again if needed.
    }
  }

  /// Explicit sign-in from Settings. Returns true on success.
  Future<bool> signInAndLink() async {
    if (_serverClientId.isEmpty) {
      debugPrint('GOOGLE_SERVER_CLIENT_ID not configured; Google Sign-In will fail.');
      return false;
    }
    try {
      final account = await _googleSignIn.signIn();
      if (account == null) return false;
      await _link(account);
      Analytics.identityLinked();
      return true;
    } on PlatformException catch (e) {
      // Common Android failures: sign_in_failed / 10 = no web client ID configured.
      debugPrint('Google Sign-In error: ${e.code} — ${e.message}');
      return false;
    } catch (e) {
      debugPrint('Google Sign-In unexpected error: $e');
      return false;
    }
  }

  /// Unlink this device from Google. Keeps the Google account, but this
  /// device becomes anonymous again.
  Future<void> unlink() async {
    await _googleSignIn.signOut();
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kLinked, false);
    Analytics.identityUnlinked();
  }

  /// Fetch the server's view of this device identity.
  Future<Map<String, dynamic>> getServerIdentity() async {
    try {
      await TgClient().ensureSession();
      return await TgClient().getIdentity();
    } catch (_) {
      return {'linked': false};
    }
  }

  Future<void> _link(GoogleSignInAccount account) async {
    final auth = await account.authentication;
    final idToken = auth.idToken;
    if (idToken == null || idToken.isEmpty) {
      throw Exception('لم يتم استلام Google ID token. تأكد من ضبط GOOGLE_SERVER_CLIENT_ID.');
    }

    await TgClient().ensureSession();
    final response = await TgClient().linkGoogleIdentity(idToken: idToken);

    // Backend must confirm the link; otherwise we must not mark as linked.
    if (response['ok'] != true) {
      final error = response['error'] ?? 'unknown';
      throw Exception('رفض الخادم ربط الحساب: $error');
    }

    final p = await SharedPreferences.getInstance();
    await p.setBool(_kLinked, true);
  }
}
