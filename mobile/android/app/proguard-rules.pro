# Flutter default rules
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Keep Dart entry points used by reflection
-keepattributes *Annotation*
-keepattributes Signature
-keepattributes Exceptions
-keepattributes InnerClasses
-keepattributes EnclosingMethod

# Firebase
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.firebase.**
-dontwarn com.google.android.gms.**

# JSON / Retrofit / Dio / http clients
-keep class com.google.gson.** { *; }
-keep class com.squareup.** { *; }
-dontwarn com.squareup.**
-dontwarn okio.**

# Keep native methods
-keepclasseswithmembernames class * {
    native <methods>;
}

# Keep Application class
-keep public class * extends android.app.Application

# Keep Flutter Local Notifications
-keep class com.dexterous.flutterlocalnotifications.** { *; }

# Keep Riverpod/Provider generated code (if any reflection)
-keep class * extends android.content.BroadcastReceiver
-keep class * extends android.app.Service

# Suppress harmless warnings for desugaring and Play Core split install
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
