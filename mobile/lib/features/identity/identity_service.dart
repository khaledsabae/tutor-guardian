/// Identity service — Phase 1.2 optional Google Sign-In.
///
/// Links a Google account to the anonymous device_id on the backend so
/// child data and referral attribution survive app reinstall. The flow is
/// opt-in only; the user can keep using the app anonymously.
library;

import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
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
    defaultValue:
        '620240456244-d7a3fd35ianuu34i1sobb0pj4ncttmdu.apps.googleusercontent.com',
  );

  final GoogleSignIn _googleSignIn = GoogleSignIn.instance;
  Future<void>? _initialization;

  // Every entry point shares the same initialization, including concurrent
  // cold-start restore and a Settings action. v7 requires exactly one call.
  Future<void> _ensureInitialized() =>
      _initialization ??= _googleSignIn.initialize(
        serverClientId: _serverClientId.isEmpty ? null : _serverClientId,
      );

  /// Returns true if a previous sign-in happened on this device.
  Future<bool> get isLinked async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_kLinked) ?? false;
  }

  /// Best-effort restore on cold start. If the user previously signed in, we
  /// attempt lightweight authentication and tell the backend to link this
  /// device_id. Google may display an account-selection sheet on Android.
  Future<void> silentRestore() async {
    if (!await isLinked) return;
    if (_serverClientId.isEmpty) return;
    try {
      await _ensureInitialized();
      final account = await _googleSignIn.attemptLightweightAuthentication();
      if (account == null) return;
      await _link(account);
    } catch (_) {
      // ignore — user will see the opt-in button again if needed.
    }
  }

  /// Explicit sign-in from Settings. Throws on network failure so the UI
  /// can show a targeted message; returns false for cancellation/interruption
  /// or a missing client ID. Other failures reach the localized error UI.
  Future<bool> signInAndLink() async {
    if (_serverClientId.isEmpty) {
      debugPrint(
        'GOOGLE_SERVER_CLIENT_ID not configured; Google Sign-In will fail.',
      );
      return false;
    }
    try {
      await _ensureInitialized();
      if (!_googleSignIn.supportsAuthenticate()) {
        throw UnsupportedError('Google Sign-In authentication is unavailable.');
      }
      // Identity uses only the ID token; no Google API scopes/access tokens or
      // server authorization code are needed, so do not request authorization.
      final account = await _googleSignIn.authenticate();
      await _link(account);
      Analytics.identityLinked();
      return true;
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled ||
          e.code == GoogleSignInExceptionCode.interrupted) {
        return false;
      }
      rethrow;
    }
  }

  /// Unlink this device from Google. Keeps the Google account, but this
  /// device becomes anonymous again.
  Future<void> unlink() async {
    await _ensureInitialized();
    await _googleSignIn.signOut();
    final p = await SharedPreferences.getInstance();
    await p.setBool(_kLinked, false);
    Analytics.identityUnlinked();
  }

  /// Link this phone to its Google account again using lightweight
  /// authentication from the CURRENT session. An Android account-selection
  /// sheet is possible. Called by account deletion right
  /// after the device proof: a link made before this build — or by a session
  /// that had not proven — is unconfirmed, and a deletion follows only
  /// confirmed links (§10), so the Google record and its backups would be
  /// kept. The server upgrades the link to confirmed when a proven session
  /// links the same account again (identity.py keeps the higher of the two).
  /// False when it could not be done; never throws.
  Future<bool> relinkSilently() async {
    if (_serverClientId.isEmpty) return false;
    try {
      await _ensureInitialized();
      // A null Future means no immediate authentication result (e.g. web).
      // Leave the link unconfirmed; account deletion must not assume success.
      final account = await _googleSignIn.attemptLightweightAuthentication();
      if (account == null) return false;
      await _link(account);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// The account was deleted (MOBILE_API §10): sign out of Google in the app
  /// so the next launch does not silently re-link a fresh install to it. The
  /// server already erased the link; nothing is sent.
  Future<void> signOutAfterAccountDeletion() async {
    try {
      await _ensureInitialized();
      await _googleSignIn.signOut();
    } catch (_) {
      // Not signed in, or no Play Services: nothing to sign out of.
    }
  }

  /// Fetch the server's view of this device identity.
  Future<Map<String, dynamic>> getServerIdentity() async {
    try {
      await TgClient.shared.ensureSession();
      return await TgClient.shared.getIdentity();
    } catch (_) {
      return {'linked': false};
    }
  }

  Future<void> _link(GoogleSignInAccount account) async {
    final auth = account.authentication;
    final idToken = auth.idToken;
    if (idToken == null || idToken.isEmpty) {
      throw Exception(
        'لم يتم استلام Google ID token. تأكد من ضبط GOOGLE_SERVER_CLIENT_ID.',
      );
    }

    await TgClient.shared.ensureSession();
    final response = await TgClient.shared.linkGoogleIdentity(idToken: idToken);

    // Backend must confirm the link; otherwise we must not mark as linked.
    if (response['ok'] != true) {
      final error = response['error'] ?? 'unknown';
      throw Exception('رفض الخادم ربط الحساب: $error');
    }

    final p = await SharedPreferences.getInstance();
    await p.setBool(_kLinked, true);
  }
}
