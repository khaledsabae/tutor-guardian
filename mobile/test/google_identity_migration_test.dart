import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/identity/identity_service.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
// Exercise the real plugin API through its platform boundary.
import 'package:google_sign_in_platform_interface/google_sign_in_platform_interface.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _GooglePlatform extends GoogleSignInPlatform {
  int initializations = 0,
      authentications = 0,
      lightweightAttempts = 0,
      signOuts = 0;
  InitParameters? initParams;
  Completer<void>? initializationGate;
  Object? initializationError;
  bool initialized = false;
  bool interactiveSupported = true;
  bool noLightweightFuture = false, noLightweightAccount = false;
  String? idToken = 'google-id-token';
  // The Google account lightweight authentication returns — on Android 7.x
  // possibly one the user picked from a sheet listing every phone account.
  String accountId = 'parent';
  Object? authenticationError, lightweightError, signOutError;
  final scopeHints = <List<String>>[];

  void reset() {
    authentications = lightweightAttempts = signOuts = 0;
    interactiveSupported = true;
    noLightweightFuture = noLightweightAccount = false;
    idToken = 'google-id-token';
    accountId = 'parent';
    authenticationError = lightweightError = signOutError = null;
    scopeHints.clear();
  }

  AuthenticationResults get account => AuthenticationResults(
    user: GoogleSignInUserData(email: '$accountId@example.com', id: accountId),
    authenticationTokens: AuthenticationTokenData(idToken: idToken),
  );

  @override
  Future<void> init(InitParameters params) async {
    initializations++;
    initParams = params;
    await initializationGate?.future;
    if (initializationError case final error?) throw error;
    initialized = true;
  }

  @override
  bool supportsAuthenticate() {
    expect(initialized, isTrue, reason: 'initialization must finish first');
    return interactiveSupported;
  }

  @override
  Future<AuthenticationResults> authenticate(
    AuthenticateParameters params,
  ) async {
    expect(initialized, isTrue, reason: 'initialization must finish first');
    authentications++;
    scopeHints.add(params.scopeHint);
    if (authenticationError case final error?) throw error;
    return account;
  }

  @override
  Future<AuthenticationResults?>? attemptLightweightAuthentication(
    AttemptLightweightAuthenticationParameters params,
  ) {
    expect(initialized, isTrue, reason: 'initialization must finish first');
    lightweightAttempts++;
    if (noLightweightFuture) return null;
    if (lightweightError case final error?) return Future.error(error);
    return Future.value(noLightweightAccount ? null : account);
  }

  @override
  Future<void> signOut(SignOutParams params) async {
    expect(initialized, isTrue, reason: 'initialization must finish first');
    signOuts++;
    if (signOutError case final error?) throw error;
  }

  // Unexpected OAuth authorization calls fail: identity needs only an ID token.
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _SessionClient extends TgClient {
  _SessionClient(http.Client client)
    : super.forTesting(baseUrl: 'https://identity.test', httpClient: client);
  @override
  Future<SessionResponse> ensureSession() async =>
      SessionResponse(sessionId: 'session', token: 'session-token');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final google = _GooglePlatform();
  final identity = IdentityService.instance;
  final requests = <http.Request>[];
  Map<String, dynamic> response = {'ok': true, 'google_id': 'parent'};
  // GET /api/identity/me — the server's view of this device's link.
  Map<String, dynamic> me = {'ok': true, 'linked': false};
  Object? backendError, meError;
  void Function()? onMe;
  final realChildModeRead = identity.readChildMode;
  Iterable<http.Request> linkRequests() =>
      requests.where((r) => r.url.path == '/api/identity/link-google');
  Iterable<http.Request> meRequests() =>
      requests.where((r) => r.url.path == '/api/identity/me');
  const linkedAsParent = {'ok': true, 'linked': true, 'google_id': 'parent'};
  setUpAll(() {
    GoogleSignInPlatform.instance = google;
  });
  setUp(() {
    google.reset();
    requests.clear();
    response = {'ok': true, 'google_id': 'parent'};
    me = {'ok': true, 'linked': false};
    backendError = meError = null;
    onMe = null;
    identity.readChildMode = realChildModeRead;
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({});
    TgClient.shared = _SessionClient(
      MockClient((request) async {
        requests.add(request);
        final isMe = request.url.path == '/api/identity/me';
        if (isMe) onMe?.call();
        if (isMe && meError != null) throw meError!;
        if (!isMe && backendError != null) throw backendError!;
        return http.Response(
          jsonEncode(isMe ? me : response),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
  });
  tearDown(() {
    TgClient.shared = null;
  });

  test(
    'concurrent sign-in and re-link await exactly one initialization',
    () async {
      me = linkedAsParent;
      google.initializationGate = Completer<void>();
      final signIn = identity.signInAndLink();
      final relink = identity.relinkSilently();
      await Future<void>.delayed(Duration.zero);
      expect(google.initializations, 1);
      expect(google.authentications, 0);
      expect(google.lightweightAttempts, 0);
      google.initializationGate!.complete();
      expect(await signIn, isTrue);
      expect(await relink, isTrue);
      expect(google.initializations, 1);
      expect(google.initParams!.serverClientId, isNotEmpty);
    },
  );
  test('a failed initialization is retried by the next attempt', () async {
    identity.resetInitializationForTesting();
    final before = google.initializations;
    google.initializationError = const GoogleSignInException(
      code: GoogleSignInExceptionCode.clientConfigurationError,
    );
    await expectLater(
      identity.signInAndLink(),
      throwsA(isA<GoogleSignInException>()),
    );
    google.initializationError = null;
    expect(await identity.signInAndLink(), isTrue);
    expect(google.initializations, before + 2);
  });
  test('missing Google ID token reaches the identity error UI', () async {
    google.idToken = null;
    await expectLater(
      identity.signInAndLink(),
      throwsA(predicate((e) => e.toString().contains('Google ID token'))),
    );
    expect(await identity.isLinked, isFalse);
    expect(requests, isEmpty);
  });
  test('empty Google ID token never reaches the backend', () async {
    google.idToken = '';
    await expectLater(identity.signInAndLink(), throwsException);
    expect(requests, isEmpty);
    expect(await identity.isLinked, isFalse);
  });
  test(
    'interactive sign-in links only the ID token after confirmation',
    () async {
      expect(await identity.signInAndLink(), isTrue);
      expect(google.authentications, 1);
      expect(google.lightweightAttempts, 0);
      expect(google.scopeHints.single, isEmpty);
      expect(requests.single.url.path, '/api/identity/link-google');
      expect(requests.single.headers['Authorization'], 'Bearer session-token');
      expect(jsonDecode(requests.single.body), {'id_token': 'google-id-token'});
      expect(await identity.isLinked, isTrue);
      // The linked account is remembered so a later silent path can refuse
      // any other account a picker hands back.
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('identity.google_id'), 'parent');
    },
  );
  for (final code in [
    GoogleSignInExceptionCode.canceled,
    GoogleSignInExceptionCode.interrupted,
  ]) {
    test('interactive $code leaves the device anonymous', () async {
      google.authenticationError = GoogleSignInException(code: code);
      expect(await identity.signInAndLink(), isFalse);
      expect(requests, isEmpty);
      expect(await identity.isLinked, isFalse);
    });
  }
  for (final code in [
    GoogleSignInExceptionCode.clientConfigurationError,
    GoogleSignInExceptionCode.providerConfigurationError,
    GoogleSignInExceptionCode.uiUnavailable,
    GoogleSignInExceptionCode.unknownError,
  ]) {
    test('interactive $code reaches the identity error UI', () async {
      final error = GoogleSignInException(code: code, description: 'failure');
      google.authenticationError = error;
      await expectLater(identity.signInAndLink(), throwsA(same(error)));
      expect(requests, isEmpty);
      expect(await identity.isLinked, isFalse);
    });
  }
  test(
    'unsupported interactive authentication does not open a picker',
    () async {
      google.interactiveSupported = false;
      await expectLater(identity.signInAndLink(), throwsUnsupportedError);
      expect(google.authentications, 0);
      expect(requests, isEmpty);
    },
  );
  test(
    'server rejection reaches UI and never persists a linked identity',
    () async {
      response = {'ok': false, 'error': 'invalid_id_token'};
      await expectLater(identity.signInAndLink(), throwsA(isA<TgApiError>()));
      expect(await identity.isLinked, isFalse);
    },
  );
  test('network failure reaches the connectivity UI', () async {
    backendError = const SocketException('offline');
    await expectLater(
      identity.signInAndLink(),
      throwsA(isA<SocketException>()),
    );
    expect(await identity.isLinked, isFalse);
  });
  test('cold start does not authenticate an anonymous installation', () async {
    await identity.silentRestore();
    expect(google.lightweightAttempts, 0);
    expect(google.authentications, 0);
    expect(requests, isEmpty);
  });
  test(
    'cold start makes no Google call when the server already has the link',
    () async {
      SharedPreferences.setMockInitialValues({'identity.linked': true});
      me = linkedAsParent;
      await identity.silentRestore();
      expect(google.lightweightAttempts, 0);
      expect(google.authentications, 0);
      expect(linkRequests(), isEmpty);
      // A device linked before this build learns its account from the server.
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('identity.google_id'), 'parent');
    },
  );
  test(
    'cold start makes no Google call when the server is unreachable',
    () async {
      SharedPreferences.setMockInitialValues({
        'identity.linked': true,
        'identity.google_id': 'parent',
      });
      meError = const SocketException('offline');
      await identity.silentRestore();
      expect(google.lightweightAttempts, 0);
      expect(linkRequests(), isEmpty);
    },
  );
  test('cold start in child mode never reaches Google or the server', () async {
    SharedPreferences.setMockInitialValues({
      'identity.linked': true,
      'identity.google_id': 'parent',
    });
    FlutterSecureStorage.setMockInitialValues({'tg_child_mode_active': '1'});
    await identity.silentRestore();
    expect(google.lightweightAttempts, 0);
    expect(google.authentications, 0);
    expect(requests, isEmpty);
  });
  test(
    'server lost the link: restore re-links the same remembered account',
    () async {
      SharedPreferences.setMockInitialValues({
        'identity.linked': true,
        'identity.google_id': 'parent',
      });
      await identity.silentRestore();
      expect(meRequests(), hasLength(1));
      expect(google.lightweightAttempts, 1);
      expect(google.authentications, 0);
      expect(jsonDecode(linkRequests().single.body), {
        'id_token': 'google-id-token',
      });
    },
  );
  test(
    'restore refuses a different account picked from the Google sheet',
    () async {
      SharedPreferences.setMockInitialValues({
        'identity.linked': true,
        'identity.google_id': 'parent',
      });
      google.accountId = 'someone-else';
      await identity.silentRestore();
      expect(google.lightweightAttempts, 1);
      // No link, so no merge of the other account's devices on the server.
      expect(linkRequests(), isEmpty);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('identity.google_id'), 'parent');
    },
  );
  test(
    'restore without a remembered account never opens a Google sheet',
    () async {
      // Linked before this build and the server no longer knows the link:
      // there is no account to compare with, so nothing is attempted.
      SharedPreferences.setMockInitialValues({'identity.linked': true});
      await identity.silentRestore();
      expect(google.lightweightAttempts, 0);
      expect(linkRequests(), isEmpty);
    },
  );
  const rememberedButServerLost = {
    'identity.linked': true,
    'identity.google_id': 'parent',
  };
  for (final (outcome, arrange) in <(String, void Function())>[
    ('no account', () => google.noLightweightAccount = true),
    (
      'a cancelled sheet',
      () => google.lightweightError = const GoogleSignInException(
        code: GoogleSignInExceptionCode.canceled,
      ),
    ),
    ('a different account', () => google.accountId = 'someone-else'),
  ]) {
    test(
      'after $outcome the sheet is not offered again on later launches',
      () async {
        SharedPreferences.setMockInitialValues(rememberedButServerLost);
        arrange();
        await identity.silentRestore(); // cold start 1
        await identity.silentRestore(); // cold start 2
        expect(google.lightweightAttempts, 1);
        expect(google.authentications, 0);
        expect(linkRequests(), isEmpty);
      },
    );
  }
  test('manual sign-in still links after silent restore gave up', () async {
    SharedPreferences.setMockInitialValues(rememberedButServerLost);
    google.noLightweightAccount = true;
    await identity.silentRestore();
    expect(await identity.signInAndLink(), isTrue);
    expect(google.authentications, 1);
    expect(linkRequests(), hasLength(1));
    // A fresh link earns the silent path one attempt again.
    google.noLightweightAccount = false;
    await identity.silentRestore();
    expect(google.lightweightAttempts, 2);
  });
  test(
    'child mode starting during the server call stops the Google call',
    () async {
      SharedPreferences.setMockInitialValues(rememberedButServerLost);
      var childMode = false;
      identity.readChildMode = () async => childMode;
      onMe = () => childMode = true;
      await identity.silentRestore();
      expect(meRequests(), hasLength(1));
      expect(google.lightweightAttempts, 0);
      expect(linkRequests(), isEmpty);
    },
  );
  test('an unreadable child-mode flag counts as child mode', () async {
    SharedPreferences.setMockInitialValues(rememberedButServerLost);
    identity.readChildMode = () async => throw Exception('keystore');
    await identity.silentRestore();
    expect(google.lightweightAttempts, 0);
    expect(requests, isEmpty);
  });
  test(
    're-link uses current-session ID token without interactive sign-in',
    () async {
      me = linkedAsParent;
      expect(await identity.relinkSilently(), isTrue);
      expect(google.lightweightAttempts, 1);
      expect(google.authentications, 0);
      expect(jsonDecode(linkRequests().single.body), {
        'id_token': 'google-id-token',
      });
    },
  );
  test(
    're-link refuses a different account so deletion cannot follow it',
    () async {
      me = linkedAsParent;
      google.accountId = 'someone-else';
      expect(await identity.relinkSilently(), isFalse);
      expect(linkRequests(), isEmpty);
    },
  );
  test(
    're-link refuses a stale remembered account the server disowns',
    () async {
      // The server is the authority for the deletion link, not local state.
      SharedPreferences.setMockInitialValues({
        'identity.linked': true,
        'identity.google_id': 'someone-else',
      });
      me = linkedAsParent;
      google.accountId = 'someone-else';
      expect(await identity.relinkSilently(), isFalse);
      expect(linkRequests(), isEmpty);
    },
  );
  test('re-link refuses an ID token issued for a different account', () async {
    String part(Object o) =>
        base64Url.encode(utf8.encode(jsonEncode(o))).replaceAll('=', '');
    me = linkedAsParent;
    google.idToken =
        '${part({'alg': 'none'})}.${part({'sub': 'someone-else'})}.sig';
    expect(await identity.relinkSilently(), isFalse);
    expect(linkRequests(), isEmpty);
  });
  test('re-link with no server link attempts nothing', () async {
    SharedPreferences.setMockInitialValues({
      'identity.linked': true,
      'identity.google_id': 'parent',
    });
    expect(await identity.relinkSilently(), isFalse);
    expect(google.lightweightAttempts, 0);
    expect(linkRequests(), isEmpty);
  });
  test('re-link with the server unreachable attempts nothing', () async {
    meError = const SocketException('offline');
    expect(await identity.relinkSilently(), isFalse);
    expect(google.lightweightAttempts, 0);
    expect(linkRequests(), isEmpty);
  });
  test('no lightweight account leaves the re-link unconfirmed', () async {
    me = linkedAsParent;
    google.noLightweightAccount = true;
    expect(await identity.relinkSilently(), isFalse);
    expect(linkRequests(), isEmpty);
  });
  test(
    'nullable lightweight Future does not hang or confirm account deletion',
    () async {
      me = linkedAsParent;
      google.noLightweightFuture = true;
      expect(await identity.relinkSilently(), isFalse);
      expect(linkRequests(), isEmpty);
    },
  );
  test(
    'lightweight failures stay best effort during restore and re-link',
    () async {
      SharedPreferences.setMockInitialValues({
        'identity.linked': true,
        'identity.google_id': 'parent',
      });
      google.lightweightError = const GoogleSignInException(
        code: GoogleSignInExceptionCode.providerConfigurationError,
      );
      await identity.silentRestore();
      me = linkedAsParent;
      expect(await identity.relinkSilently(), isFalse);
      expect(google.lightweightAttempts, 2);
      expect(linkRequests(), isEmpty);
      expect(google.authentications, 0);
    },
  );
  test('unlink signs out and clears the local linked flag', () async {
    identity.resetInitializationForTesting();
    final before = google.initializations;
    SharedPreferences.setMockInitialValues({
      'identity.linked': true,
      'identity.google_id': 'parent',
    });
    await identity.unlink();
    expect(google.signOuts, 1);
    expect(await identity.isLinked, isFalse);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('identity.google_id'), isNull);
    expect(requests, isEmpty);
    expect(google.initializations, before + 1);
  });
  test(
    'account deletion sign-out is best effort with no backend re-link',
    () async {
      identity.resetInitializationForTesting();
      final before = google.initializations;
      google.signOutError = const GoogleSignInException(
        code: GoogleSignInExceptionCode.providerConfigurationError,
      );
      await identity.signOutAfterAccountDeletion();
      expect(google.signOuts, 1);
      expect(requests, isEmpty);
      expect(google.initializations, before + 1);
    },
  );
}
