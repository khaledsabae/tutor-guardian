/// Identity service — Phase 1.2 optional Google Sign-In.
///
/// Links a Google account to the anonymous device_id on the backend so
/// child data and referral attribution survive app reinstall. The flow is
/// opt-in only; the user can keep using the app anonymously.
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../api/tg_client.dart';
import '../../core/analytics.dart';
import '../routine/services/child_mode_secure_storage.dart'
    as child_mode_storage;

class IdentityService {
  IdentityService._();
  static final IdentityService instance = IdentityService._();

  static const _kLinked = 'identity.linked';

  /// The Google account (`sub`) this device was linked to. On Android 7.x
  /// lightweight authentication can fall back to a sheet listing every
  /// account on the phone, so the silent paths only ever re-link this one.
  static const _kGoogleId = 'identity.google_id';

  /// Set once cold-start restore has used its one silent Google attempt for
  /// a link the server lost. Without it a reinstall that only got the
  /// preferences back would offer the account sheet on every launch. Only a
  /// successful link clears it; the identity screen still signs in.
  static const _kSilentRestoreSpent = 'identity.silent_restore_spent';

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
  // A failed initialization is forgotten so the next attempt retries instead
  // of replaying the cached failure for the rest of the process.
  Future<void> _ensureInitialized() {
    final pending = _initialization ??= _googleSignIn
        .initialize(
          serverClientId: _serverClientId.isEmpty ? null : _serverClientId,
        )
        .catchError((Object e, StackTrace st) {
          _initialization = null;
          return Future<void>.error(e, st);
        });
    return pending;
  }

  @visibleForTesting
  void resetInitializationForTesting() => _initialization = null;

  /// Reads the child-mode flag; may throw. Replaceable in tests.
  @visibleForTesting
  Future<bool> Function() readChildMode =
      child_mode_storage.readChildModeActive;

  /// Child mode, failing closed: an unreadable flag counts as child mode.
  Future<bool> _inChildMode() async {
    try {
      return await readChildMode();
    } catch (_) {
      return true;
    }
  }

  /// Returns true if a previous sign-in happened on this device.
  Future<bool> get isLinked async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_kLinked) ?? false;
  }

  /// Best-effort restore on cold start, for a device that was linked before.
  ///
  /// Asks the server first: when it still has the link — every ordinary
  /// cold start — nothing touches Google. Only when the server has lost it
  /// (a reinstall that kept this app's preferences) is lightweight
  /// authentication attempted, and only the account this device was linked
  /// to is accepted: on Android it may show a sheet listing every account on
  /// the phone, and linking another one would merge that account's devices.
  /// Never runs in child mode, and does nothing if the server is unreachable.
  Future<void> silentRestore() async {
    if (!await isLinked) return;
    if (_serverClientId.isEmpty) return;
    if (await _inChildMode()) return;
    try {
      final me = await _fetchServerIdentity();
      final prefs = await SharedPreferences.getInstance();
      if (me['linked'] == true) {
        // A link made before this build: remember which account it is.
        final serverId = _googleIdOf(me);
        if (serverId != null && prefs.getString(_kGoogleId) == null) {
          await prefs.setString(_kGoogleId, serverId);
        }
        return;
      }
      final expected = prefs.getString(_kGoogleId);
      if (expected == null || expected.isEmpty) return;
      if (prefs.getBool(_kSilentRestoreSpent) ?? false) return;
      await _ensureInitialized();
      // Child mode may have started while the server answered.
      if (await _inChildMode()) return;
      // Spent before asking: a null, cancelled or wrong-account answer — or
      // a crash mid-sheet — must not bring the sheet back next launch.
      await prefs.setBool(_kSilentRestoreSpent, true);
      final account = await _googleSignIn.attemptLightweightAuthentication();
      if (account == null) return;
      if (!_isAccount(account, expected)) {
        debugPrint('identity: restore refused a different Google account');
        return;
      }
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
    await p.remove(_kGoogleId);
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
      // Only the account the server already links this device to may be
      // confirmed: a picker could hand back any account on the phone, and
      // the deletion would then follow that account to its phones.
      final expected = _googleIdOf(await _fetchServerIdentity());
      if (expected == null) return false;
      await _ensureInitialized();
      // A null Future means no immediate authentication result (e.g. web).
      // Leave the link unconfirmed; account deletion must not assume success.
      final account = await _googleSignIn.attemptLightweightAuthentication();
      if (account == null) return false;
      if (!_isAccount(account, expected)) {
        debugPrint('identity: re-link refused a different Google account');
        return false;
      }
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

  /// `GET /api/identity/me`, letting failures through: a silent path must
  /// not read "unreachable" as "not linked".
  Future<Map<String, dynamic>> _fetchServerIdentity() async {
    await TgClient.shared.ensureSession();
    return TgClient.shared.getIdentity();
  }

  static String? _googleIdOf(Map<String, dynamic> me) {
    if (me['linked'] != true) return null;
    final id = me['google_id'];
    return id is String && id.isNotEmpty ? id : null;
  }

  /// Whether [account] is the Google account [googleId]. The server links the
  /// ID token's `sub`, so that is checked too whenever the token is readable.
  static bool _isAccount(GoogleSignInAccount account, String googleId) {
    if (account.id != googleId) return false;
    final sub = _subjectOf(account.authentication.idToken);
    return sub == null || sub == googleId;
  }

  static String? _subjectOf(String? idToken) {
    final parts = idToken?.split('.');
    if (parts == null || parts.length != 3) return null;
    try {
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      );
      final sub = payload is Map ? payload['sub'] : null;
      return sub is String ? sub : null;
    } catch (_) {
      return null;
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
    await p.remove(_kSilentRestoreSpent);
    final linkedId = response['google_id'];
    await p.setString(
      _kGoogleId,
      linkedId is String && linkedId.isNotEmpty ? linkedId : account.id,
    );
  }
}
