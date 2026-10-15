// «نور والقناديل», phase 4 — «المساعد»: Noor beside every answer (thinking
// while it is written, calm once done), «سأجرّبها مع …» under the latest
// answer that has a step, and the severity chip only when it matters.
//
// The answers in the first group are real ones — excerpts of replies the
// pipeline wrote in the 2026-06-12 evaluation run
// (ops/eval/runs/phase23local_20260612_2023.jsonl), cut after the items the
// extractor reads. The step is what the parent will see read back to them.

import 'package:almorabbi/api/tg_client.dart';
import 'package:almorabbi/features/child_memory/data/memory_repository.dart';
import 'package:almorabbi/features/child_memory/data/placeholder_names.dart';
import 'package:almorabbi/features/child_memory/providers/memory_providers.dart';
import 'package:almorabbi/features/companion/data/companion_store.dart';
import 'package:almorabbi/features/companion/logic/answer_step.dart';
import 'package:almorabbi/features/companion/providers/companion_providers.dart';
import 'package:almorabbi/features/companion/widgets/noor_face.dart';
import 'package:almorabbi/features/companion/widgets/noor_presence.dart';
import 'package:almorabbi/features/onboarding/data/onboarding_storage.dart';
import 'package:almorabbi/features/onboarding/providers/onboarding_providers.dart';
import 'package:almorabbi/l10n/app_localizations.dart';
import 'package:almorabbi/models/api_models.dart';
import 'package:almorabbi/screens/chat_screen.dart';
import 'package:almorabbi/state/chat_notifier.dart';
import 'package:almorabbi/widgets/message_bubble.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

// g-019 — label, then a sentence that opens with «أولًا،».
const _g019 = '''### الخطوات العملية لحل هذه المشكلة:

1. **توضيح الأهمية:** أولًا، يجب عليك توضيح أهمية احترام حقوق الآخرين للطفل. هذا يعني أن كل شخص له حقوقه الخاصة ويجب على الجميع التأكد من عدم المساس بها.

2. **التعليم والتدريب:** ثانياً، يمكنك تعليم ولدك عن حقوق الآخرين وفوائدها. يمكن أن يكون ذلك من خلال قصص إسلامية أو أفلام تربوية تحكي قصة شخص يحافظ على حقوق الآخرين ويكون مثالًا للآخرين.''';

// g-026 — a label alone; the step is its first sub-item.
const _g026 = '''### خطوات عملية مرقّمة للتعامل مع هذه الحالة

1. **التواصل والتفهم**:
   - تحدث مع بنتك بشكل مباشر وصريح، دون إخفاء أي شيء.
   - اشرح لها أن هذا النوع من الأسئلة طبيعي في سنها، وأنها ليست فعلاً مشكلة، بل هي جزء من نموها العقلي والفكري.''';

// g-070 — the first item is a referral to the doctor; the step is the next.
const _g070 = '''بناءً على المعلومات الواردة في المصادر المذكورة، يبدو أن سلوك ابنك طبيعي ويعتبر جزءًا من التطور الطبيعي للطفل في عمر السنتين. في هذا العمر، الأطفال يتعلمون التنقل والحركة بكثافة، وقد يكونون أقل قدرة على البقاء مقيدين لفترة طويلة.

خطوات عملية:

1. **التواصل مع الطبيب**: إذا كنت تشعر بالقلق بشأن سلوك ابنك، من الأفضل أن تتواصل مع طبيبك للحصول على رأيه الشخصي والتأكد من صحة الطفل.
2. **اللعب والقراءة**: استمر في اللعب وقراءة الكتب للأطفال لطفلك. هذه النشاطات تعزز التواصل اللغوي وتزيد من حركة الطفل.
3. **تشجيع التواصل**: قم بتشجيع ابنك على استخدام الكلمات التي يعرفها، حتى لو كانت قليلة. هذا يساعد في تطوير مهاراته اللغوية.

### 📚 المصادر: Morgan et al., Journal of Speech, Language, and Hearing Research · medical · Children and Mental Health — NIMH''';

// g-097 — the first sentence runs past 120 characters, label and all.
const _g097 = '''**الخطوات العملية المرقّمة لتحسين تأثير الشاشات على تركيز الطفل خلال الأنشطة الأخرى:**

1. **تحديد وقت معين**: اختر وقتًا محددًا في اليوم للطفل يمكنه فيه الاستمتاع بالأفلام والبرامج التلفزيونية دون تداخل مع المهام المدرسية أو المنزلية.
2. **فصل الأنشطة**: حدد أوقات معينة لمشاهدة التلفاز أو اللعب على الهواتف الذكية، واحتفظ باوقات أخرى للأنشطة الأخرى مثل الدراسة أو التحدث مع الآخرين.''';

// g-104 — a refusal: no list, nothing to promise.
const _g104 = '''عذرًا على الإرباك، ولكن المعلومات حول كمية الأنسولين التي يجب إعطاؤها قبل الغداء لطفل عمره 4-6 سنوات مصاب بالسكري النوع الأول غير متاحة في المصادر المذكورة. يُنصح بمراجعة المتخصصين الصحيين للحصول على التوجيهات الطبية المناسبة لهذا العمر والحالة الصحية الخاصة بالطفل.

📚 المصادر: medical · National Institute of Mental Health (NIMH) · Disruptive Mood Dysregulation Disorder — NIMH''';

AssistantReply _reply({
  String severity = 'متوسط',
  String mode = 'llm_generated',
  String text = 'x',
}) => AssistantReply.fromJson({
  'reply_text': text,
  'domain': 'islamic_parenting',
  'severity': severity,
  'needs_human_review': false,
  'escalation_target': null,
  'mode': mode,
  'session_id': 's1',
});

ChatMessageUI _answer(String id, String text, {String severity = 'متوسط'}) =>
    ChatMessageUI(id: id, role: 'assistant', content: text)
      ..reply = _reply(severity: severity, text: text);

ChatMessageUI _question(String id) =>
    ChatMessageUI(id: id, role: 'user', content: 'سؤال');

Widget _host(Widget child, {bool reduceMotion = false}) => MaterialApp(
  locale: const Locale('ar'),
  localizationsDelegates: AppLocalizations.localizationsDelegates,
  supportedLocales: AppLocalizations.supportedLocales,
  home: Builder(
    builder: (context) => MediaQuery(
      data: MediaQuery.of(context).copyWith(disableAnimations: reduceMotion),
      child: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  ),
);

void main() {
  group('the step an answer offers', () {
    test('label and the first sentence, the ordinal dropped (g-019)', () {
      expect(
        promiseStepFromAnswer(_g019),
        'توضيح الأهمية: يجب عليك توضيح أهمية احترام حقوق الآخرين للطفل',
      );
    });

    test('a label alone gives way to its first sub-item (g-026)', () {
      expect(
        promiseStepFromAnswer(_g026),
        'تحدث مع بنتك بشكل مباشر وصريح، دون إخفاء أي شيء',
      );
    });

    test('a referral is skipped for the next item (g-070)', () {
      expect(
        promiseStepFromAnswer(_g070),
        'اللعب والقراءة: استمر في اللعب وقراءة الكتب للأطفال لطفلك',
      );
    });

    test('a long sentence is cut at a word, within 120 (g-097)', () {
      final step = promiseStepFromAnswer(_g097)!;
      expect(step.length, lessThanOrEqualTo(kPromiseStepMax));
      expect(step, startsWith('تحديد وقت معين: اختر وقتًا محددًا في اليوم'));
      expect(step, endsWith('…'));
    });

    test('a refusal has no step (g-104)', () {
      expect(promiseStepFromAnswer(_g104), isNull);
    });

    test('citations and markdown do not reach the step', () {
      const answer = '''الصدق يُبنى بالأمان قبل العقاب.

1. **امدح صدقه أولًا** 【1】: حين يعترف بخطأ، اشكره على صدقه قبل أي تعليق على الخطأ.
2. **اجعل الاعتراف سهلًا**: لا تسأله سؤالًا تعرف جوابه.

📚 المصادر: منهج التربية النبوية''';
      expect(
        promiseStepFromAnswer(answer),
        'امدح صدقه أولًا: حين يعترف بخطأ، اشكره على صدقه قبل أي تعليق على الخطأ',
      );
    });

    test('English answers work the same way', () {
      const answer = '''Bedtime fights usually ease with a fixed routine.

1. **Start a wind-down routine**: Dim the lights 30 minutes before bed and read one short story together.
2. **Keep screens out of the bedroom.**

📚 Sources: AAP''';
      expect(
        promiseStepFromAnswer(answer),
        'Start a wind-down routine: Dim the lights 30 minutes before bed and '
        'read one short story together',
      );
    });

    test('a list that is only sources or warning signs gives nothing', () {
      expect(
        promiseStepFromAnswer('''الجواب قصير.

### متى تراجع متخصصاً
- هل يرفض الطعام لأكثر من يومين؟
- إذا ظهرت حرارة مرتفعة.'''),
        isNull,
      );
      expect(
        promiseStepFromAnswer('''الجواب قصير.

### المصادر:
- تربية الأولاد في الإسلام - علوان'''),
        isNull,
      );
      expect(promiseStepFromAnswer('نص بلا قائمة ولا خطوات.'), isNull);
    });

    test('a condition is not cut away from what to do about it', () {
      final long = 'إذا لاحظت نوبات غضب حادة ومتكررة لدى طفلك في البيت وفي '
          'المدرسة وعند الزيارات العائلية وفي السوق وفي أوقات النوم، '
          'فاجلس معه بعد أن يهدأ.';
      expect(promiseStepFromAnswer('1. $long'), isNull);
      expect(
        promiseStepFromAnswer('1. إذا غضب، اطلب منه أن يأخذ نفسًا عميقًا.'),
        'إذا غضب، اطلب منه أن يأخذ نفسًا عميقًا',
      );
    });
  });

  group('trimStep — what the server is sent', () {
    test('a clause cut that keeps a whole thought', () {
      final s = 'اجلس معه كل مساء عشر دقائق بلا هاتف ولا تلفاز ولا مقاطعة، '
          'واسأله عن أجمل ما حدث في يومه وعن أصعب ما مرّ به، ثم أنصت '
          'إليه حتى يفرغ';
      final out = trimStep(s);
      expect(out.length, lessThanOrEqualTo(kPromiseStepMax));
      expect(out, 'اجلس معه كل مساء عشر دقائق بلا هاتف ولا تلفاز ولا مقاطعة، '
          'واسأله عن أجمل ما حدث في يومه وعن أصعب ما مرّ به');
    });

    test('never a condition without its consequence', () {
      // A real lesson step (try_this) longer than the server's 120.
      const s = 'هذا الأسبوع: حين يصدق طفلك في أمرٍ صعب يخاف فيه العقاب من '
          'أبيه أو أمه أو معلمه، امدح صدقه أولاً بكلمة واضحة قبل أن تعالج '
          'الخطأ نفسه بهدوء وحزم';
      expect(s.length, greaterThan(kPromiseStepMax));
      final out = trimStep(s);
      expect(out.length, lessThanOrEqualTo(kPromiseStepMax));
      // The clause break before «امدح» would end on the condition alone.
      expect(out, endsWith('…'));
      expect(out, contains('امدح'));
    });
  });

  group('names never leave the phone', () {
    const family = [
      FamilyMember(id: 7, name: 'سارة'),
      FamilyMember(id: 9, name: 'عبد الرحمن'),
      FamilyMember(id: 11, name: 'طفلي'),
    ];

    test('the child is «طفلي», a sibling its letter, prefixes stay', () {
      expect(
        redactFamilyNames('اجلس مع سارة ولسارة وقت مع عبد الرحمن',
            family: family, subjectId: 7),
        'اجلس مع طفلي ولطفلي وقت مع الطفل ب',
      );
    });

    test('spellings and harakat fold; other words are left alone', () {
      expect(
        redactFamilyNames('امدح ساره وسارةُ، لا محمد', family: const [
          FamilyMember(id: 7, name: 'سارة'),
          FamilyMember(id: 8, name: 'حمد'),
        ], subjectId: 7),
        'امدح طفلي وطفلي، لا محمد',
      );
    });

    test('an only child is «طفلي»; Latin names fold case', () {
      expect(
        redactFamilyNames('Read with ADAM tonight; Adam\'s turn',
            family: const [FamilyMember(id: 3, name: 'Adam')]),
        'Read with طفلي tonight; طفلي\'s turn',
      );
    });

    test('a default name is not a name', () {
      expect(
        redactFamilyNames('طفلي يحب القصص',
            family: const [FamilyMember(id: 1, name: 'طفلي')], subjectId: 1),
        'طفلي يحب القصص',
      );
    });
  });

  group('Noor beside the answer', () {
    testWidgets('thinks while the answer is written, then rests calm',
        (t) async {
      final m = ChatMessageUI(
          id: '1', role: 'assistant', content: '', isStreaming: true);
      await t.pumpWidget(_host(MessageBubble(message: m)));
      expect(find.text('🧑‍🏫'), findsNothing);
      expect(t.widget<NoorFace>(find.byType(NoorFace)).state,
          NoorFaceState.thinking);
      expect(t.state<NoorFaceWidgetState>(find.byType(NoorFace)).cycling,
          isTrue);

      m
        ..content = 'إجابة'
        ..isStreaming = false
        ..reply = _reply();
      await t.pumpWidget(_host(MessageBubble(message: m)));
      expect(t.widget<NoorFace>(find.byType(NoorFace)).state,
          NoorFaceState.calm);
      // Done: nothing loops — a conversation is not a column of blinking faces.
      expect(t.state<NoorFaceWidgetState>(find.byType(NoorFace)).cycling,
          isFalse);
      expect(t.state<NoorPresenceState>(find.byType(NoorPresence)).haloLooping,
          isFalse);
    });

    testWidgets('reduced motion holds the thinking face still', (t) async {
      final m = ChatMessageUI(
          id: '1', role: 'assistant', content: 'جزء', isStreaming: true);
      await t.pumpWidget(
          _host(MessageBubble(message: m), reduceMotion: true));
      expect(t.widget<NoorFace>(find.byType(NoorFace)).state,
          NoorFaceState.thinking);
      expect(t.state<NoorFaceWidgetState>(find.byType(NoorFace)).cycling,
          isFalse);
      // Settle the bubble so no timer outlives the test.
      m
        ..isStreaming = false
        ..reply = _reply();
      await t.pumpWidget(
          _host(MessageBubble(message: m), reduceMotion: true));
    });
  });

  group('severity chip', () {
    for (final (wire, shown) in const [
      ('خفيف', false),
      ('متوسط', false),
      ('شديد', true),
      ('طارئ', true),
    ]) {
      testWidgets('«$wire» ${shown ? 'is shown' : 'is hidden'}', (t) async {
        await t.pumpWidget(_host(
            MessageBubble(message: _answer('a', 'إجابة', severity: wire))));
        expect(find.text(wire), shown ? findsOneWidget : findsNothing);
      });
    }
  });

  group('«سأجرّبها مع …» in the chat', () {
    Future<(ProviderContainer, _FakeMemoryRepo)> pumpChat(
      WidgetTester t,
      List<ChatMessageUI> messages, {
      String childName = 'سارة',
    }) async {
      // A 360 dp phone, tall enough that every bubble is built.
      t.view.physicalSize = const Size(360 * 3, 2400 * 3);
      t.view.devicePixelRatio = 3;
      addTearDown(t.view.reset);
      SharedPreferences.setMockInitialValues({});
      final prefs = await SharedPreferences.getInstance();
      final storage = OnboardingStorage(prefs);
      await storage.markOnboardingCompleted();
      await storage.setActiveChild(id: 7, name: childName, ageGroup: '4-6');
      final repo = _FakeMemoryRepo();
      final container = ProviderContainer(overrides: [
        tgClientProvider.overrideWithValue(_NullClient()),
        sharedPreferencesProvider.overrideWith((_) async => prefs),
        memoryRepositoryProvider.overrideWithValue(repo),
        chatNotifierProvider.overrideWith((ref) => _SeededChat(messages)),
      ]);
      await container.read(sharedPreferencesProvider.future);
      addTearDown(container.dispose);
      await t.pumpWidget(UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          locale: const Locale('ar'),
          localizationsDelegates: AppLocalizations.localizationsDelegates,
          supportedLocales: AppLocalizations.supportedLocales,
          home: const ChatScreen(),
        ),
      ));
      await t.pump(const Duration(milliseconds: 400));
      return (container, repo);
    }

    // Two answers with a step each, the second naming the child.
    final named = '''1. **اجلس مع سارة قبل النوم**: واسألها عن أجمل ما حدث في يومها.
2. **أنصت دون مقاطعة.**''';

    testWidgets('only under the latest answer', (t) async {
      await pumpChat(t, [
        _question('q1'),
        _answer('a1', _g019),
        _question('q2'),
        _answer('a2', named),
      ]);
      final chip = find.text('سأجرّبها مع سارة');
      expect(chip, findsOneWidget);
      expect(
        find.ancestor(
          of: chip,
          matching: find.byWidgetPredicate(
              (w) => w is MessageBubble && w.message.id == 'a2'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('no chip when the latest answer has no usable step',
        (t) async {
      await pumpChat(t, [
        _question('q1'),
        _answer('a1', _g019),
        _question('q2'),
        _answer('a2', _g104),
      ]);
      expect(find.textContaining('سأجرّبها'), findsNothing);
    });

    testWidgets('no chip under an emergency answer', (t) async {
      await pumpChat(t, [_question('q1'), _answer('a1', named, severity: 'طارئ')]);
      expect(find.textContaining('سأجرّبها'), findsNothing);
    });

    testWidgets('the default name is not said; the parent says «طفلي»',
        (t) async {
      await pumpChat(t, [_question('q1'), _answer('a1', _g026)],
          childName: 'طفلي');
      await t.tap(find.text('سأجرّبها مع طفلي'));
      await t.pumpAndSettle();
      // Noor's question, in Noor's voice.
      expect(find.text('متى ستجرّبها مع طفلك؟'), findsOneWidget);
      expect(find.text('تحدث مع بنتك بشكل مباشر وصريح، دون إخفاء أي شيء'),
          findsOneWidget);
    });

    testWidgets('a slot keeps the promise; the server never sees the name',
        (t) async {
      final (container, repo) = await pumpChat(t, [
        _question('q1'),
        _answer('a1', named),
      ]);
      await container.read(companionMemoryProvider.future);

      await t.tap(find.text('سأجرّبها مع سارة'));
      await t.pumpAndSettle();
      expect(find.text('خطوتك من هذه الإجابة'), findsOneWidget);
      await t.tap(find.text('غدًا'));
      await t.pumpAndSettle();
      for (var i = 0; i < 5; i++) {
        await t.pump(const Duration(milliseconds: 50));
      }

      const step =
          'اجلس مع سارة قبل النوم: واسألها عن أجمل ما حدث في يومها';
      final promises =
          container.read(companionMemoryProvider).requireValue.promises;
      expect(promises, hasLength(1));
      expect(promises.single.step, step); // as the parent read it
      expect(promises.single.childId, 7);
      expect(promises.single.slot, PromiseSlot.tomorrow);
      expect(promises.single.followupId, 42);

      expect(repo.opened, hasLength(1));
      expect(repo.opened.single.childId, 7);
      expect(repo.opened.single.when, 'tomorrow');
      expect(repo.opened.single.step,
          'اجلس مع طفلي قبل النوم: واسألها عن أجمل ما حدث في يومها');
      expect(repo.opened.single.step, isNot(contains('سارة')));

      // Kept: the chip says so and offers no second promise.
      expect(find.text('سأجرّبها مع سارة'), findsNothing);
      expect(find.text('سأسألك كيف جرت.'), findsOneWidget);
    });
  });
}

class _SeededChat extends ChatNotifier {
  _SeededChat(List<ChatMessageUI> messages) : super(_NullClient()) {
    state = ChatState(messages: messages, sessionId: 's1');
  }

  @override
  Future<void> bootstrap() async {}
}

class _FakeMemoryRepo implements MemoryRepository {
  final opened = <({int childId, String step, String when})>[];

  @override
  Future<int?> openPromise(int childId,
      {required String step, required String when, String topic = 'other'}) async {
    opened.add((childId: childId, step: step, when: when));
    return 42;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _NullClient extends TgClient {
  _NullClient() : super.forTesting(baseUrl: 'http://test');

  @override
  Future<SessionResponse> createSession({Map<String, dynamic>? metadata}) async =>
      throw const TgApiError(500, 'fake-error');

  @override
  Future<String?> currentSessionId() async =>
      throw const TgApiError(500, 'fake-error');

  @override
  Future<SessionHistory> getHistory(String sessionId) async =>
      throw const TgApiError(500, 'fake-error');
}
