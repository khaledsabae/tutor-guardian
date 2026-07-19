# ──────────────────────────────────────────────────────────────
# Tutor Guardian — Narrowed R8 rules
#
# What we removed and why:
#   - io.flutter.**     → flutter_proguard_rules.pro (in Flutter SDK) already
#                          keeps FlutterPlugin impls. The AOT-compiled Dart
#                          kernel is untouched by R8. Consumer rules from the
#                          Gradle plugin cover the rest.
#   - com.google.firebase/gms.** → Firebase AARs ship their own consumer-rules.
#                          The broad -keep { *; } was the #1 reason R8 could
#                          not shrink/optimize (~20 MB dex that should be ~4 MB).
#   - com.google.gson.** broad → replaced with targeted rules below.
#   - com.squareup.** broad → OkHttp/Retrofit ship their own consumer rules.
#   - extends Application/Receiver/Service → AAPT manifest rules + plugin
#                          manifest entries already preserve these.
#
# What we keep:
#   1. Gson runtime reflection — flutter_local_notifications bundles
#      gson:2.8.9 but ships NO consumer rules. It uses TypeToken and
#      @SerializedName for serializing NotificationDetails to JSON.
#   2. Crashlytics line numbers — SourceFile + LineNumberTable for readable
#      stack traces in Firebase Crashlytics.
#   3. Native methods — standard JNI keep.
#   4. dontwarn — harmless desugaring / Play Core / BackEvent warnings.
# ──────────────────────────────────────────────────────────────

# --- Gson (flutter_local_notifications:2.8.9 has no consumer rules) ---
-keepattributes Signature
-keepattributes *Annotation*
-keep class com.google.gson.reflect.TypeToken { *; }
-keep class * extends com.google.gson.reflect.TypeToken
-keepclassmembers,allowobfuscation class * {
    @com.google.gson.annotations.SerializedName <fields>;
}
-keep,allowobfuscation,allowshrinking class com.google.gson.reflect.TypeToken
-keep,allowobfuscation,allowshrinking class * extends com.google.gson.reflect.TypeToken

# --- Firebase Crashlytics (no consumer rules in AAR) ---
# Firebase Crashlytics registers via ComponentRegistrar SPI and its internal
# classes are only reachable through reflection. Keep the full package to
# prevent R8 from stripping the component registration chain.
-keep class com.google.firebase.crashlytics.** { *; }
-keep class * implements com.google.firebase.components.ComponentRegistrar { *; }

# --- Crashlytics: readable stack traces ---
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# --- Native methods ---
-keepclasseswithmembernames class * {
    native <methods>;
}

# --- Suppress harmless warnings ---
-dontwarn java.lang.invoke.**
-dontwarn javax.annotation.**
-dontwarn org.conscrypt.**
-dontwarn com.google.android.play.core.**
-dontwarn com.google.android.gms.common.**
-dontwarn android.window.BackEvent
-dontwarn android.window.OnBackInvokedDispatcher
-dontwarn android.window.OnBackInvokedCallback
-dontwarn androidx.window.**
-dontwarn org.slf4j.**
-dontwarn com.facebook.**
