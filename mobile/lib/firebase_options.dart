// Generated from google-services.json — do not edit manually.
// Re-generate by running: flutterfire configure
import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) throw UnsupportedError('Web not configured.');
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        throw UnsupportedError('iOS not configured yet.');
      default:
        throw UnsupportedError(
            'Unsupported platform: $defaultTargetPlatform');
    }
  }

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyBkRIIv6s_k4UlDfJSncO2WJk_goDkTnt0',
    appId: '1:620240456244:android:68d74a2b062c14e4751861',
    messagingSenderId: '620240456244',
    projectId: 'almorabbi',
    storageBucket: 'almorabbi.firebasestorage.app',
  );
}
