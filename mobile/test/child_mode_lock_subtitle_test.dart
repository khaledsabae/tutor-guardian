// The PIN screen says what to do in each of its four states. It used to show
// «المرحلة العمرية» on first setup and «غير متصل بالإنترنت» everywhere else.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/features/routine/screens/child_mode_lock_screen.dart';

final _store = <String, String>{};

Future<void> _pump(WidgetTester tester, Widget screen) async {
  await tester.pumpWidget(ProviderScope(
    child: MaterialApp(
      locale: const Locale('ar'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: screen,
    ),
  ));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async {
        final key = call.arguments['key'] as String?;
        switch (call.method) {
          case 'read':
            return _store[key];
          case 'write':
            _store[key!] = call.arguments['value'] as String;
            return null;
          case 'delete':
            _store.remove(key);
            return null;
          default:
            return null;
        }
      },
    );
  });
  tearDown(_store.clear);

  testWidgets('first setup asks for a new PIN, then for the same PIN again',
      (tester) async {
    await _pump(tester, const ChildModeLockScreen(childId: 1, childName: 'أحمد'));
    expect(find.text('اختر رمزًا من أربعة أرقام يحمي وضع الطفل. ستحتاج إليه للخروج منه.'),
        findsOneWidget);
    expect(find.text('المرحلة العمرية'), findsNothing);

    for (final d in ['1', '2', '3', '4']) {
      await tester.tap(find.text(d).last);
      await tester.pump();
    }
    expect(find.text('أدخل الرمز مرة أخرى للتأكيد.'), findsOneWidget);
  });

  testWidgets('with a PIN set, entering asks for it before the hand-over',
      (tester) async {
    _store['tg_child_mode_pin_hash'] = 'stored';
    await _pump(tester, const ChildModeLockScreen(childId: 1, childName: 'أحمد'));
    expect(find.text('أدخل رمز وضع الطفل ثم سلّم الهاتف لطفلك.'), findsOneWidget);
    expect(find.text('غير متصل بالإنترنت'), findsNothing);
  });

  testWidgets('leaving child mode asks for the PIN to leave', (tester) async {
    _store['tg_child_mode_pin_hash'] = 'stored';
    await _pump(tester, const ChildModeLockScreen(childId: 1, childName: 'أحمد', isExit: true));
    expect(find.text('أدخل الرمز للخروج من وضع الطفل.'), findsOneWidget);
    expect(find.text('غير متصل بالإنترنت'), findsNothing);
  });
}
