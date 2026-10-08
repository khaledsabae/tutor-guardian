plugins {
    id("com.android.application")
    id("dev.flutter.flutter-gradle-plugin")
    id("com.google.gms.google-services")
    id("com.google.firebase.crashlytics")
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

// Explicit build-only switch, with a guard against accidental local use.
// Environment values are not an authentication boundary; the workflow owns gating.
val ciUnsignedAab = System.getenv("TG_CI_UNSIGNED_AAB") == "true"
check(!ciUnsignedAab || System.getenv("GITHUB_ACTIONS") == "true") {
    "Unsigned release flag is restricted to hosted CI"
}

android {
    namespace = "com.alsaba.almorabbi"
    // Pinned to 36: newer P1 plugins (flutter_plugin_android_lifecycle,
    // shared_preferences_android, url_launcher_android + androidx.core 1.17)
    // require compileSdk 36, above the Flutter default.
    compileSdk = 36
    ndkVersion = flutter.ndkVersion

    compileOptions {
        isCoreLibraryDesugaringEnabled = true
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Tutor Guardian — mobile app
        applicationId = "com.alsaba.almorabbi"
        // Flutter 3.44.1 supplies minSdk 24, also required by the Google
        // Sign-In 7 Android implementation (Firebase BoM 34 requires 23).
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
            signingConfig = if (ciUnsignedAab) {
                null
            } else if (keystoreProperties.getProperty("storeFile") != null) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("debug")
            }
            // Retain full Flutter release ABIs and normal production shrinking.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")
    // Required by Activity.enableEdgeToEdge() for backward-compatible
    // edge-to-edge rendering across Android versions.
    implementation("androidx.activity:activity:1.9.3")
}
