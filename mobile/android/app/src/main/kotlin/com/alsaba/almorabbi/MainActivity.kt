package com.alsaba.almorabbi

import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterFragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        // After an account deletion the app must really end, not hide: on
        // Android 12+ SystemNavigator.pop() / Back only moves a root task to
        // the back, so the engine — and the deleted account's state in the
        // Dart isolate — would survive and come back on the next open.
        // finishAndRemoveTask() destroys this activity, and with it the
        // engine it created (this activity never uses a cached engine), so
        // the next launch runs main() from nothing. lib/core/app_closer.dart.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, APP_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "finishAndRemoveTask" -> {
                        result.success(true)
                        finishAndRemoveTask()
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private companion object {
        const val APP_CHANNEL = "almorabbi/app"
    }
}
