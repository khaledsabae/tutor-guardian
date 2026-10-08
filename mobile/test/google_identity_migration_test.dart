import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/identity/identity_service.dart';
import 'package:almorabbi/models/api_models.dart';
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
  bool initialized = false;
  bool interactiveSupported = true;
  bool noLightweightFuture = false, noLightweightAccount = false;
  String? idToken = 'google-id-token';
  Object? authenticationError, lightweightError, signOutError;
  final scopeHints = <List<String>>[];

  void reset() {
    authentications = lightweightAttempts = signOuts = 0;
    interactiveSupported = true;
    noLightweightFuture = noLightweightAccount = false;
    idToken = 'google-id-token';
    authenticationError = lightweightError = signOutError = null;
    scopeHints.clear();
  }

  AuthenticationResults get account => AuthenticationResults(
    user: const GoogleSignInUserData(email: 'parent@example.com', id: 'parent'),
    authenticationTokens: AuthenticationTokenData(idToken: idToken),
  );

  @override
  Future<void> init(InitParameters params) async {
    initializations++;
    initParams = params;
    await initializationGate?.future;
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
  Map<String, dynamic> response = {'ok': true};
  Object? backendError;
  setUpAll(() {
    GoogleSignInPlatform.instance = google;
  });
  setUp(() {
    google.reset();
    requests.clear();
    response = {'ok': true};
    backendError = null;
    SharedPreferences.setMockInitialValues({});
    TgClient.shared = _SessionClient(
      MockClient((request) async {
        requests.add(request);
        if (backendError case final error?) throw error;
        return http.Response(
          jsonEncode(response),
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
    'previously linked cold start uses lightweight authentication',
    () async {
      SharedPreferences.setMockInitialValues({'identity.linked': true});
      await identity.silentRestore();
      expect(google.lightweightAttempts, 1);
      expect(google.authentications, 0);
      expect(requests.single.url.path, '/api/identity/link-google');
    },
  );
  test(
    're-link uses current-session ID token without interactive sign-in',
    () async {
      expect(await identity.relinkSilently(), isTrue);
      expect(google.lightweightAttempts, 1);
      expect(google.authentications, 0);
      expect(jsonDecode(requests.single.body), {'id_token': 'google-id-token'});
    },
  );
  test('no lightweight account leaves the re-link unconfirmed', () async {
    google.noLightweightAccount = true;
    expect(await identity.relinkSilently(), isFalse);
    expect(requests, isEmpty);
  });
  test(
    'nullable lightweight Future does not hang or confirm account deletion',
    () async {
      google.noLightweightFuture = true;
      expect(await identity.relinkSilently(), isFalse);
      expect(requests, isEmpty);
    },
  );
  test(
    'lightweight failures stay best effort during restore and re-link',
    () async {
      SharedPreferences.setMockInitialValues({'identity.linked': true});
      google.lightweightError = const GoogleSignInException(
        code: GoogleSignInExceptionCode.providerConfigurationError,
      );
      await identity.silentRestore();
      expect(await identity.relinkSilently(), isFalse);
      expect(requests, isEmpty);
      expect(google.authentications, 0);
    },
  );
  test('unlink signs out and clears the local linked flag', () async {
    SharedPreferences.setMockInitialValues({'identity.linked': true});
    await identity.unlink();
    expect(google.signOuts, 1);
    expect(await identity.isLinked, isFalse);
    expect(requests, isEmpty);
    expect(google.initializations, 1);
  });
  test(
    'account deletion sign-out is best effort with no backend re-link',
    () async {
      google.signOutError = const GoogleSignInException(
        code: GoogleSignInExceptionCode.providerConfigurationError,
      );
      await identity.signOutAfterAccountDeletion();
      expect(google.signOuts, 1);
      expect(requests, isEmpty);
      expect(google.initializations, 1);
    },
  );
}
