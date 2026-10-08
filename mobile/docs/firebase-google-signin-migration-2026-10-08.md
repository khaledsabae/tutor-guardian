# Firebase and Google Sign-In major migration

Checked against stable pub.dev releases on 2026-10-08. Android remains the
configured production platform; `firebase_options.dart` does not configure iOS.

| Package | Previous lock | New minimum / lock |
| --- | --- | --- |
| firebase_core | 3.15.2 | 4.15.0 |
| firebase_analytics | 11.6.0 | 12.6.0 |
| firebase_messaging | 15.2.10 | 16.7.0 |
| firebase_crashlytics | 4.3.10 | 5.4.0 |
| google_sign_in | 6.3.0 | 7.2.0 |

## Breaking changes and application handling

Read each package's changelog across the versions above:
[Core](https://pub.dev/packages/firebase_core/changelog),
[Analytics](https://pub.dev/packages/firebase_analytics/changelog),
[Messaging](https://pub.dev/packages/firebase_messaging/changelog),
[Crashlytics](https://pub.dev/packages/firebase_crashlytics/changelog), and
[Google Sign-In](https://pub.dev/packages/google_sign_in/changelog).
Also read the [Google Sign-In migration guide](https://github.com/flutter/packages/blob/main/packages/google_sign_in/google_sign_in/MIGRATION.md)
and [Android integration guide](https://pub.dev/packages/google_sign_in_android).
Native requirements were checked against
[Firebase Android releases](https://firebase.google.com/support/release-notes/android),
[Firebase Apple releases](https://firebase.google.com/support/release-notes/ios), and
[Crashlytics Gradle v3 requirements](https://firebase.google.com/docs/crashlytics/upgrade-to-crashlytics-gradle-plugin-v3).

### Firebase

- All four Firebase majors move to Android BoM 34 and Apple SDK 12. The resolved
  Core release selects Android BoM 34.19.0 and Apple SDK 12.19.0.
- Android now requires at least API 23 and Java 17. Flutter 3.44.1 supplies API
  24 through `flutter.minSdkVersion`, which also satisfies Google Sign-In's
  Android implementation. compileSdk 36, AGP 9.0.1, Gradle 9.1.0, Kotlin 2.3.20,
  and the Java/Kotlin 17 targets already meet the packages' requirements.
  The existing AGP compatibility flags and plugin compileSdk override remain.
- Apple SDK 12 requires iOS 15.0. Raise all three Xcode project deployment
  targets from 13.0 to 15.0. This aligns dependency requirements; it does not
  provision an iOS Firebase app or claim an iOS build was verified.
  Native Apple SDK builds require Xcode 16.2+ with the Swift 6 toolchain;
  deprecated Analytics AdIdSupport/WithoutAdIdSupport subspecs and removed
  OnDeviceConversion subspec/targets and Dynamic Links APIs have no callers or
  custom CocoaPods configuration here.
- Analytics 12 removes `setCurrentScreen` and `logSetCheckoutOption`. The app
  already uses `logScreenView`, `logEvent`, and `setUserProperty`; no removed
  method is called. Event names, parameter types, and collection policy remain.
- Messaging 16 removes upstream `sendMessage` (upstream FCM messaging). The
  app uses downstream FCM only: permissions, get/delete token, refresh stream,
  foreground messages, background entry point, and notification taps. Those
  APIs remain. The chat notifier's unrelated `sendMessage` is not an FCM API.
- Core initialization and Crashlytics recording/collection APIs used here
  remain compatible. Firebase is still initialized in both the main isolate
  and the existing annotated background FCM entry point. Latest native plugin
  Kotlin/Swift, Pigeon, and UIScene changes require native CI validation; the
  iOS runner already uses Flutter's scene lifecycle.
- Firebase BoM 34 removes separate KTX artifacts; the app has no explicit KTX
  dependency to migrate. No release signing or R8 changes are required. Keep
  the existing `ComponentRegistrar` keep rule, including constructors, and
  Crashlytics rules: release startup is part of the hosted CI evidence.

### Google Sign-In

- Replace the constructed client with `GoogleSignIn.instance`; initialize
  once, await initialization before every native operation, and pass the
  existing web OAuth `serverClientId` to `initialize`.
- Replace interactive `signIn` with `authenticate`. Successful authentication
  returns an account; cancellation is now a typed `GoogleSignInException`,
  rather than a null account. Handle cancellation/configuration cases without
  marking the device linked, and surface meaningful failures to the UI.
- Replace `signInSilently` with `attemptLightweightAuthentication`, respecting
  its nullable Future result. Restore/relink remain best effort and do not
  invoke interactive `authenticate`. Lightweight authentication can still
  display an account-selection sheet on Android; it is not guaranteed silent.
- `account.authentication` is synchronous and exposes the ID token only.
  Continue sending the ID token to the backend's existing identity-link API;
  write the local linked flag only after the backend confirms success.
- Authentication and Google API authorization are separate. Constructor
  scopes, authentication access tokens, and `requestScopes` are removed.
  The app needs only identity, so remove the email/profile scopes and do not
  request Google API authorization. If a future feature accesses Google APIs,
  use `account.authorizationClient.authorizationForScopes` and, following a
  user action when required, `authorizeScopes`; server authorization uses
  `authorizeServer`. No access token/server authorization code is needed here.
- The plugin no longer maintains app-level current-user state. This app uses
  returned accounts and backend identity instead of `currentUser` or
  `onCurrentUserChanged`; it has no such deprecated state to migrate.
- Android now uses Credential Manager / Google Identity instead of the
  deprecated Android Google Sign-In SDK. Preserve the web server client ID,
  package registration, and signing fingerprints. A cancellation result can
  also mask Android OAuth configuration errors, so native tests must exercise
  both correct and deliberately incorrect configuration.
  The resolved Android plugin ships its own resource keep for
  `default_web_client_id`; no broader application R8/resource rule is needed.

## Hosted emulator acceptance

Existing `Mobile E2E` runs release APKs with R8 on API 35 for fresh install and
in-place upgrade (13 journeys), capturing native/Dart errors, ANRs, and restart
data continuity. These journeys do **not** authenticate a Google account,
verify GA4 delivery, or send FCM messages. CI APKs explicitly deactivate
Analytics collection to avoid polluting production; `debug.firebase.analytics.app`
alone does not override that flag. Their success is startup/upgrade evidence,
not proof of the three integrations below.

Use a hosted integration environment with a disposable Google account, its
OAuth fingerprints registered for the CI signing certificate, and isolated
Firebase/backend test data. Required evidence before release:

- **Sign-in:** fresh anonymous use still works; cancel leaves identity unlinked;
  successful Credential Manager authentication yields a nonempty ID token
  accepted by the backend; linked profile and child data persist on restart
  and in-place upgrade; unlink and account deletion do not silently recreate
  a deleted link. Exercise revoked credentials, invalid OAuth configuration,
  missing token, and backend/network failure without a crash or false success.
- **Analytics:** in a separate test Firebase project with collection enabled,
  prove intended screen/funnel/identity events reach DebugView once with the
  existing valid parameters; verify collection disabled really sends nothing.
  Do not remove the production-data protection from the default CI APKs.
- **Push:** on a Play Services emulator, allow and deny Android 13+ permission;
  prove token registration/refresh associates the correct device; deliver
  foreground/background/terminated test messages and verify notification
  channels, the background isolate, and tap routing; cold start/upgrade must
  keep identity and child data; deletion removes token registration. Capture
  logcat to catch missing Firebase registrars, native errors, and ANRs.
- **Crashlytics:** confirm release initialization and nonfatal reporting in
  isolated test data, with mapping upload from the existing CI plugin/signing
  configuration. Never deliberately crash a production user session.

No APK/AAB build or emulator is run locally for this migration. Dart service
tests cover initialization ordering, token/link failures, cancellation,
lightweight restore, and sign-out; they cannot prove Credential Manager UI,
native Firebase registration, server OAuth configuration, or remote delivery.
