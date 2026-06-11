plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

import java.util.Properties

// Read the local signing config if it exists. We never commit key.properties
// (see android/.gitignore + repo .gitignore), so on a fresh clone the
// `release` build falls back to the debug keystore — which is fine for
// local smoke testing, but **production Play Store uploads MUST use the
// real keystore**. Run `flutter build appbundle --release` after creating
// android/app/key.properties + android/app/almorabbi-upload.jks.
val keystoreProperties: Properties = Properties().apply {
    val f = rootProject.file("app/key.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "com.alsaba.almorabbi"
    // Pinned to 35: newer P1 plugins (share_plus / file_picker →
    // flutter_plugin_android_lifecycle) require a compileSdk above the
    // Flutter default. Bumped from flutter.compileSdkVersion in the P1 build.
    compileSdk = 35
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Tutor Guardian — mobile app
        applicationId = "com.alsaba.almorabbi"
        // minSdk 23 = Android 6.0 (covers >99% of active devices and is
        // required by several modern Flutter plugins).
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    // Production signing — only applies when app/key.properties exists.
    signingConfigs {
        create("release") {
            if (keystoreProperties.getProperty("storeFile") != null) {
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
            }
        }
    }

    buildTypes {
        release {
            // Use the real upload keystore if key.properties is present;
            // otherwise fall back to the debug key (still works for
            // `flutter build appbundle --release` on a fresh machine).
            signingConfig = if (keystoreProperties.getProperty("storeFile") != null) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
            // Strip unused ABIs / split per ABI for smaller artefacts.
            // (Re-enable if you want a fat AAB; not needed for Play.)
            isMinifyEnabled = false
            isShrinkResources = false
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
