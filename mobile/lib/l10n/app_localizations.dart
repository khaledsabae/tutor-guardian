import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('en'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In ar, this message translates to:
  /// **'المربي الذكي'**
  String get appTitle;

  /// No description provided for @appName.
  ///
  /// In ar, this message translates to:
  /// **'المربّي'**
  String get appName;

  /// No description provided for @navToday.
  ///
  /// In ar, this message translates to:
  /// **'اليوم'**
  String get navToday;

  /// No description provided for @navMyPaths.
  ///
  /// In ar, this message translates to:
  /// **'مساراتي'**
  String get navMyPaths;

  /// No description provided for @navAdhkar.
  ///
  /// In ar, this message translates to:
  /// **'الورد'**
  String get navAdhkar;

  /// No description provided for @navAssistant.
  ///
  /// In ar, this message translates to:
  /// **'المساعد'**
  String get navAssistant;

  /// No description provided for @navDailyTracker.
  ///
  /// In ar, this message translates to:
  /// **'حساب اليوم'**
  String get navDailyTracker;

  /// No description provided for @navHabitBalance.
  ///
  /// In ar, this message translates to:
  /// **'ميزان العادات'**
  String get navHabitBalance;

  /// No description provided for @save.
  ///
  /// In ar, this message translates to:
  /// **'حفظ'**
  String get save;

  /// No description provided for @cancel.
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get cancel;

  /// No description provided for @ok.
  ///
  /// In ar, this message translates to:
  /// **'موافق'**
  String get ok;

  /// No description provided for @confirm.
  ///
  /// In ar, this message translates to:
  /// **'تأكيد'**
  String get confirm;

  /// No description provided for @yes.
  ///
  /// In ar, this message translates to:
  /// **'نعم'**
  String get yes;

  /// No description provided for @no.
  ///
  /// In ar, this message translates to:
  /// **'لا'**
  String get no;

  /// No description provided for @back.
  ///
  /// In ar, this message translates to:
  /// **'رجوع'**
  String get back;

  /// No description provided for @next.
  ///
  /// In ar, this message translates to:
  /// **'التالي'**
  String get next;

  /// No description provided for @skip.
  ///
  /// In ar, this message translates to:
  /// **'تخطي'**
  String get skip;

  /// No description provided for @retry.
  ///
  /// In ar, this message translates to:
  /// **'إعادة المحاولة'**
  String get retry;

  /// No description provided for @edit.
  ///
  /// In ar, this message translates to:
  /// **'تعديل'**
  String get edit;

  /// No description provided for @delete.
  ///
  /// In ar, this message translates to:
  /// **'حذف'**
  String get delete;

  /// No description provided for @share.
  ///
  /// In ar, this message translates to:
  /// **'مشاركة'**
  String get share;

  /// No description provided for @search.
  ///
  /// In ar, this message translates to:
  /// **'بحث'**
  String get search;

  /// No description provided for @add.
  ///
  /// In ar, this message translates to:
  /// **'إضافة'**
  String get add;

  /// No description provided for @close.
  ///
  /// In ar, this message translates to:
  /// **'إغلاق'**
  String get close;

  /// No description provided for @done.
  ///
  /// In ar, this message translates to:
  /// **'تم'**
  String get done;

  /// No description provided for @loading.
  ///
  /// In ar, this message translates to:
  /// **'جاري التحميل...'**
  String get loading;

  /// No description provided for @settings.
  ///
  /// In ar, this message translates to:
  /// **'الإعدادات'**
  String get settings;

  /// No description provided for @profile.
  ///
  /// In ar, this message translates to:
  /// **'الملف الشخصي'**
  String get profile;

  /// No description provided for @notifications.
  ///
  /// In ar, this message translates to:
  /// **'الإشعارات'**
  String get notifications;

  /// No description provided for @privacy.
  ///
  /// In ar, this message translates to:
  /// **'الخصوصية'**
  String get privacy;

  /// No description provided for @about.
  ///
  /// In ar, this message translates to:
  /// **'عن التطبيق'**
  String get about;

  /// No description provided for @version.
  ///
  /// In ar, this message translates to:
  /// **'النسخة'**
  String get version;

  /// No description provided for @language.
  ///
  /// In ar, this message translates to:
  /// **'اللغة'**
  String get language;

  /// No description provided for @arabic.
  ///
  /// In ar, this message translates to:
  /// **'العربية'**
  String get arabic;

  /// No description provided for @english.
  ///
  /// In ar, this message translates to:
  /// **'الإنجليزية'**
  String get english;

  /// No description provided for @welcomeToAlMurabbi.
  ///
  /// In ar, this message translates to:
  /// **'مرحبًا بك في المربي'**
  String get welcomeToAlMurabbi;

  /// No description provided for @startYourJourney.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ رحلتك'**
  String get startYourJourney;

  /// No description provided for @chooseYourChild.
  ///
  /// In ar, this message translates to:
  /// **'اختر طفلك'**
  String get chooseYourChild;

  /// No description provided for @addChild.
  ///
  /// In ar, this message translates to:
  /// **'أضف طفلك'**
  String get addChild;

  /// No description provided for @childName.
  ///
  /// In ar, this message translates to:
  /// **'اسم الطفل'**
  String get childName;

  /// No description provided for @childAge.
  ///
  /// In ar, this message translates to:
  /// **'عمر الطفل'**
  String get childAge;

  /// No description provided for @dateOfBirth.
  ///
  /// In ar, this message translates to:
  /// **'تاريخ الميلاد'**
  String get dateOfBirth;

  /// No description provided for @nextStep.
  ///
  /// In ar, this message translates to:
  /// **'التالي'**
  String get nextStep;

  /// No description provided for @previousStep.
  ///
  /// In ar, this message translates to:
  /// **'السابق'**
  String get previousStep;

  /// No description provided for @welcome.
  ///
  /// In ar, this message translates to:
  /// **'مرحباً'**
  String get welcome;

  /// No description provided for @whatsNewToday.
  ///
  /// In ar, this message translates to:
  /// **'ما الجديد اليوم؟'**
  String get whatsNewToday;

  /// No description provided for @suggestionsForYou.
  ///
  /// In ar, this message translates to:
  /// **'اقتراحات لك'**
  String get suggestionsForYou;

  /// No description provided for @startLearning.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ التعلم'**
  String get startLearning;

  /// No description provided for @trackYourProgress.
  ///
  /// In ar, this message translates to:
  /// **'تابع تقدمك'**
  String get trackYourProgress;

  /// No description provided for @goodMorning.
  ///
  /// In ar, this message translates to:
  /// **'صباح الخير'**
  String get goodMorning;

  /// No description provided for @goodEvening.
  ///
  /// In ar, this message translates to:
  /// **'مساء الخير'**
  String get goodEvening;

  /// No description provided for @askAlMurabbi.
  ///
  /// In ar, this message translates to:
  /// **'اسأل المربي'**
  String get askAlMurabbi;

  /// No description provided for @typeYourQuestion.
  ///
  /// In ar, this message translates to:
  /// **'اكتب سؤالك هنا...'**
  String get typeYourQuestion;

  /// No description provided for @thinking.
  ///
  /// In ar, this message translates to:
  /// **'جاري التفكير...'**
  String get thinking;

  /// No description provided for @errorRetryMessage.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ. حاول مرة أخرى.'**
  String get errorRetryMessage;

  /// No description provided for @dailyLimitReached.
  ///
  /// In ar, this message translates to:
  /// **'وصلنا لحدّ اليوم من الأسئلة — نستكمل غدًا بإذن الله 🌙'**
  String get dailyLimitReached;

  /// No description provided for @send.
  ///
  /// In ar, this message translates to:
  /// **'إرسال'**
  String get send;

  /// No description provided for @noActiveSession.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد جلسة نشطة. أنشئ جلسة أولاً.'**
  String get noActiveSession;

  /// No description provided for @educationalPaths.
  ///
  /// In ar, this message translates to:
  /// **'المسارات التربوية'**
  String get educationalPaths;

  /// No description provided for @startPath.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ المسار'**
  String get startPath;

  /// No description provided for @completed.
  ///
  /// In ar, this message translates to:
  /// **'مكتمل'**
  String get completed;

  /// No description provided for @lessons.
  ///
  /// In ar, this message translates to:
  /// **'الدروس'**
  String get lessons;

  /// No description provided for @podcasts.
  ///
  /// In ar, this message translates to:
  /// **'البودكاست'**
  String get podcasts;

  /// No description provided for @videos.
  ///
  /// In ar, this message translates to:
  /// **'الفيديوهات'**
  String get videos;

  /// No description provided for @quizzes.
  ///
  /// In ar, this message translates to:
  /// **'الاختبارات'**
  String get quizzes;

  /// No description provided for @flashcards.
  ///
  /// In ar, this message translates to:
  /// **'البطاقات التعليمية'**
  String get flashcards;

  /// No description provided for @holyQuran.
  ///
  /// In ar, this message translates to:
  /// **'القرآن الكريم'**
  String get holyQuran;

  /// No description provided for @surah.
  ///
  /// In ar, this message translates to:
  /// **'سورة'**
  String get surah;

  /// No description provided for @verse.
  ///
  /// In ar, this message translates to:
  /// **'آية'**
  String get verse;

  /// No description provided for @recitation.
  ///
  /// In ar, this message translates to:
  /// **'التلاوة'**
  String get recitation;

  /// No description provided for @memorization.
  ///
  /// In ar, this message translates to:
  /// **'الحفظ'**
  String get memorization;

  /// No description provided for @childJourney.
  ///
  /// In ar, this message translates to:
  /// **'رحلة طفلك'**
  String get childJourney;

  /// No description provided for @faithMilestones.
  ///
  /// In ar, this message translates to:
  /// **'محطات الإيمان'**
  String get faithMilestones;

  /// No description provided for @firstPrayer.
  ///
  /// In ar, this message translates to:
  /// **'أول صلاة'**
  String get firstPrayer;

  /// No description provided for @firstFast.
  ///
  /// In ar, this message translates to:
  /// **'أول صيام'**
  String get firstFast;

  /// No description provided for @quranMemorization.
  ///
  /// In ar, this message translates to:
  /// **'حفظ القرآن'**
  String get quranMemorization;

  /// No description provided for @educationalGames.
  ///
  /// In ar, this message translates to:
  /// **'الألعاب التعليمية'**
  String get educationalGames;

  /// No description provided for @healthyHero.
  ///
  /// In ar, this message translates to:
  /// **'بطل الصحة'**
  String get healthyHero;

  /// No description provided for @treeOfDeeds.
  ///
  /// In ar, this message translates to:
  /// **'شجرة الأعمال'**
  String get treeOfDeeds;

  /// No description provided for @emotionMaze.
  ///
  /// In ar, this message translates to:
  /// **'متاهة المشاعر'**
  String get emotionMaze;

  /// No description provided for @dataDefender.
  ///
  /// In ar, this message translates to:
  /// **'حارس البيانات'**
  String get dataDefender;

  /// No description provided for @childMode.
  ///
  /// In ar, this message translates to:
  /// **'وضع الطفل'**
  String get childMode;

  /// No description provided for @darkMode.
  ///
  /// In ar, this message translates to:
  /// **'الوضع الليلي'**
  String get darkMode;

  /// No description provided for @logout.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الخروج'**
  String get logout;

  /// No description provided for @deleteAccount.
  ///
  /// In ar, this message translates to:
  /// **'حذف الحساب'**
  String get deleteAccount;

  /// No description provided for @privacyPolicy.
  ///
  /// In ar, this message translates to:
  /// **'سياسة الخصوصية'**
  String get privacyPolicy;

  /// No description provided for @rateApp.
  ///
  /// In ar, this message translates to:
  /// **'تقييم التطبيق'**
  String get rateApp;

  /// No description provided for @shareApp.
  ///
  /// In ar, this message translates to:
  /// **'مشاركة التطبيق'**
  String get shareApp;

  /// No description provided for @contactUs.
  ///
  /// In ar, this message translates to:
  /// **'تواصل معنا'**
  String get contactUs;

  /// No description provided for @coins.
  ///
  /// In ar, this message translates to:
  /// **'العملات'**
  String get coins;

  /// No description provided for @store.
  ///
  /// In ar, this message translates to:
  /// **'المتجر'**
  String get store;

  /// No description provided for @stories.
  ///
  /// In ar, this message translates to:
  /// **'القصص'**
  String get stories;

  /// No description provided for @badges.
  ///
  /// In ar, this message translates to:
  /// **'الشعارات'**
  String get badges;

  /// No description provided for @covenant.
  ///
  /// In ar, this message translates to:
  /// **'العهد'**
  String get covenant;

  /// No description provided for @sendFeedback.
  ///
  /// In ar, this message translates to:
  /// **'أرسل ملاحظاتك'**
  String get sendFeedback;

  /// No description provided for @howWasExperience.
  ///
  /// In ar, this message translates to:
  /// **'كيف تجربتك؟'**
  String get howWasExperience;

  /// No description provided for @inviteFriend.
  ///
  /// In ar, this message translates to:
  /// **'ادعُ صديقك'**
  String get inviteFriend;

  /// No description provided for @shareTheApp.
  ///
  /// In ar, this message translates to:
  /// **'شارك التطبيق'**
  String get shareTheApp;

  /// No description provided for @getCoins.
  ///
  /// In ar, this message translates to:
  /// **'احصل على عملات'**
  String get getCoins;

  /// No description provided for @noInternetConnection.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد اتصال بالإنترنت'**
  String get noInternetConnection;

  /// No description provided for @checkConnection.
  ///
  /// In ar, this message translates to:
  /// **'تحقق من اتصالك وحاول مرة أخرى'**
  String get checkConnection;

  /// No description provided for @unexpectedError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ غير متوقع'**
  String get unexpectedError;

  /// No description provided for @noResultsFound.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد نتائج'**
  String get noResultsFound;

  /// No description provided for @agePregnancyTo1Year.
  ///
  /// In ar, this message translates to:
  /// **'الحمل - سنة'**
  String get agePregnancyTo1Year;

  /// No description provided for @age2to3.
  ///
  /// In ar, this message translates to:
  /// **'٢ - ٣ سنوات'**
  String get age2to3;

  /// No description provided for @age4to6.
  ///
  /// In ar, this message translates to:
  /// **'٤ - ٦ سنوات'**
  String get age4to6;

  /// No description provided for @age7to9.
  ///
  /// In ar, this message translates to:
  /// **'٧ - ٩ سنوات'**
  String get age7to9;

  /// No description provided for @age10to12.
  ///
  /// In ar, this message translates to:
  /// **'١٠ - ١٢ سنة'**
  String get age10to12;

  /// No description provided for @age13to15.
  ///
  /// In ar, this message translates to:
  /// **'١٣ - ١٥ سنة'**
  String get age13to15;

  /// No description provided for @age16to18.
  ///
  /// In ar, this message translates to:
  /// **'١٦ - ١٨ سنة'**
  String get age16to18;

  /// No description provided for @islamicEducation.
  ///
  /// In ar, this message translates to:
  /// **'تربية إسلامية'**
  String get islamicEducation;

  /// No description provided for @childDevelopment.
  ///
  /// In ar, this message translates to:
  /// **'تطوير الطفل'**
  String get childDevelopment;

  /// No description provided for @digitalSafety.
  ///
  /// In ar, this message translates to:
  /// **'الأمان الرقمي'**
  String get digitalSafety;

  /// No description provided for @childHealth.
  ///
  /// In ar, this message translates to:
  /// **'صحة الطفل'**
  String get childHealth;

  /// No description provided for @freeCompletely.
  ///
  /// In ar, this message translates to:
  /// **'مجاني بالكامل — بلا إعلانات ولا اشتراكات'**
  String get freeCompletely;

  /// No description provided for @noAds.
  ///
  /// In ar, this message translates to:
  /// **'بلا إعلانات'**
  String get noAds;

  /// No description provided for @noSubscriptions.
  ///
  /// In ar, this message translates to:
  /// **'بلا اشتراكات'**
  String get noSubscriptions;

  /// No description provided for @forSakeOfAllah.
  ///
  /// In ar, this message translates to:
  /// **'عمل لوجه الله'**
  String get forSakeOfAllah;

  /// No description provided for @today.
  ///
  /// In ar, this message translates to:
  /// **'اليوم'**
  String get today;

  /// No description provided for @yesterday.
  ///
  /// In ar, this message translates to:
  /// **'أمس'**
  String get yesterday;

  /// No description provided for @thisWeek.
  ///
  /// In ar, this message translates to:
  /// **'هذا الأسبوع'**
  String get thisWeek;

  /// No description provided for @thisMonth.
  ///
  /// In ar, this message translates to:
  /// **'هذا الشهر'**
  String get thisMonth;

  /// No description provided for @forceUpdateTitle.
  ///
  /// In ar, this message translates to:
  /// **'تحديث جديد وهام متاح!'**
  String get forceUpdateTitle;

  /// No description provided for @forceUpdateMessage.
  ///
  /// In ar, this message translates to:
  /// **'لقد قمنا بإضافة ميزات رائعة وإصلاحات هامة لتحسين تجربتك وضمان استقرار التطبيق. يرجى التحديث للمتابعة.'**
  String get forceUpdateMessage;

  /// No description provided for @forceUpdateButton.
  ///
  /// In ar, this message translates to:
  /// **'تحديث التطبيق الآن'**
  String get forceUpdateButton;

  /// No description provided for @bootError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تشغيل التطبيق.'**
  String get bootError;

  /// No description provided for @sessionExpired.
  ///
  /// In ar, this message translates to:
  /// **'انتهت صلاحية الجلسة.'**
  String get sessionExpired;

  /// No description provided for @serverError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ في الخادم.'**
  String get serverError;

  /// No description provided for @connectionTimeout.
  ///
  /// In ar, this message translates to:
  /// **'انتهت مهلة الاتصال بالخادم.'**
  String get connectionTimeout;

  /// No description provided for @incompleteResponse.
  ///
  /// In ar, this message translates to:
  /// **'استجابة الخادم غير مكتملة.'**
  String get incompleteResponse;

  /// No description provided for @continuePath.
  ///
  /// In ar, this message translates to:
  /// **'استمر'**
  String get continuePath;

  /// No description provided for @todaySun.
  ///
  /// In ar, this message translates to:
  /// **'اليوم ☀️'**
  String get todaySun;

  /// No description provided for @shareOpinion.
  ///
  /// In ar, this message translates to:
  /// **'شاركنا رأيك'**
  String get shareOpinion;

  /// No description provided for @searchTooltip.
  ///
  /// In ar, this message translates to:
  /// **'بحث'**
  String get searchTooltip;

  /// No description provided for @settingsTooltip.
  ///
  /// In ar, this message translates to:
  /// **'الإعدادات'**
  String get settingsTooltip;

  /// No description provided for @greetingPeace.
  ///
  /// In ar, this message translates to:
  /// **'السلام عليكم'**
  String get greetingPeace;

  /// No description provided for @greetingWithName.
  ///
  /// In ar, this message translates to:
  /// **'السلام عليكم\nرحلة {name} مستمرة'**
  String greetingWithName(Object name);

  /// No description provided for @feedbackMessage.
  ///
  /// In ar, this message translates to:
  /// **'رأيك يهمنا! شاركنا أي ملاحظة أو مشكلة — كتابةً أو صوتاً.'**
  String get feedbackMessage;

  /// No description provided for @bedtimeStories.
  ///
  /// In ar, this message translates to:
  /// **'حكايات قبل النوم'**
  String get bedtimeStories;

  /// No description provided for @bedtimeStoriesDesc.
  ///
  /// In ar, this message translates to:
  /// **'قصص قصيرة وهادئة مع صوت طبيعي للنوم 🐦'**
  String get bedtimeStoriesDesc;

  /// No description provided for @consecutiveDays.
  ///
  /// In ar, this message translates to:
  /// **'أيام متتالية'**
  String get consecutiveDays;

  /// No description provided for @completedLesson.
  ///
  /// In ar, this message translates to:
  /// **'درس مكتمل'**
  String get completedLesson;

  /// No description provided for @achievements.
  ///
  /// In ar, this message translates to:
  /// **'إنجازات'**
  String get achievements;

  /// No description provided for @startFirstPath.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ مسارك الأول'**
  String get startFirstPath;

  /// No description provided for @startFirstPathDesc.
  ///
  /// In ar, this message translates to:
  /// **'اختر رحلة تربوية قصيرة مصممة لعمر طفلك وابدأ اليوم.'**
  String get startFirstPathDesc;

  /// No description provided for @browsePaths.
  ///
  /// In ar, this message translates to:
  /// **'استعرض المسارات'**
  String get browsePaths;

  /// No description provided for @continueJourney.
  ///
  /// In ar, this message translates to:
  /// **'أكمل رحلتك'**
  String get continueJourney;

  /// No description provided for @lessonsRemaining_one.
  ///
  /// In ar, this message translates to:
  /// **'🏆 درس واحد باقٍ!'**
  String get lessonsRemaining_one;

  /// No description provided for @lessonsRemaining_other.
  ///
  /// In ar, this message translates to:
  /// **'🏆 {count} دروس باقية'**
  String lessonsRemaining_other(Object count);

  /// No description provided for @continueBtn.
  ///
  /// In ar, this message translates to:
  /// **'متابعة'**
  String get continueBtn;

  /// No description provided for @quizTitle.
  ///
  /// In ar, this message translates to:
  /// **'اختبر معلوماتك التربوية'**
  String get quizTitle;

  /// No description provided for @quizDesc.
  ///
  /// In ar, this message translates to:
  /// **'10 أسئلة سريعة • تعلّم وأنت تلعب'**
  String get quizDesc;

  /// No description provided for @askQuestion.
  ///
  /// In ar, this message translates to:
  /// **'عندك سؤال تربوي؟'**
  String get askQuestion;

  /// No description provided for @askAlMurabbiNow.
  ///
  /// In ar, this message translates to:
  /// **'اسأل المربي الذكي الآن'**
  String get askAlMurabbiNow;

  /// No description provided for @insightsTitle.
  ///
  /// In ar, this message translates to:
  /// **'تحليلات وتوصيات تربوية ذكية'**
  String get insightsTitle;

  /// No description provided for @insightsDesc.
  ///
  /// In ar, this message translates to:
  /// **'اطلع على تحليلات عادات طفلك ونشاطه'**
  String get insightsDesc;

  /// No description provided for @chatPreviousChats.
  ///
  /// In ar, this message translates to:
  /// **'المحادثات السابقة'**
  String get chatPreviousChats;

  /// No description provided for @chatAlMurabbiTitle.
  ///
  /// In ar, this message translates to:
  /// **'🛡️  المربي الذكي'**
  String get chatAlMurabbiTitle;

  /// No description provided for @chatStartNew.
  ///
  /// In ar, this message translates to:
  /// **'بدء محادثة جديدة'**
  String get chatStartNew;

  /// No description provided for @chatStartNewConfirm.
  ///
  /// In ar, this message translates to:
  /// **'بدء محادثة جديدة؟'**
  String get chatStartNewConfirm;

  /// No description provided for @chatStartNewDesc.
  ///
  /// In ar, this message translates to:
  /// **'سيتم إنهاء المحادثة الحالية وبدء جلسة جديدة على الخادم.'**
  String get chatStartNewDesc;

  /// No description provided for @chatBehaviorType.
  ///
  /// In ar, this message translates to:
  /// **'نوع السلوك (اختياري)'**
  String get chatBehaviorType;

  /// No description provided for @chatRetry.
  ///
  /// In ar, this message translates to:
  /// **'إعادة المحاولة'**
  String get chatRetry;

  /// No description provided for @chatInitSession.
  ///
  /// In ar, this message translates to:
  /// **'جاري تهيئة الجلسة…'**
  String get chatInitSession;

  /// No description provided for @chatOffline.
  ///
  /// In ar, this message translates to:
  /// **'غير متصل بالإنترنت'**
  String get chatOffline;

  /// No description provided for @chatQ_sleep.
  ///
  /// In ar, this message translates to:
  /// **'طفلي يرفض النوم ويستيقظ كثيرًا بالليل'**
  String get chatQ_sleep;

  /// No description provided for @chatQ_stubborn.
  ///
  /// In ar, this message translates to:
  /// **'ابني كثير العناد ونوبات الغضب'**
  String get chatQ_stubborn;

  /// No description provided for @chatQ_eating.
  ///
  /// In ar, this message translates to:
  /// **'طفلي يرفض الأكل — أعمل إيه؟'**
  String get chatQ_eating;

  /// No description provided for @chatQ_speech.
  ///
  /// In ar, this message translates to:
  /// **'طفلي تأخر في الكلام — متى أقلق؟'**
  String get chatQ_speech;

  /// No description provided for @chatQ_pray5.
  ///
  /// In ar, this message translates to:
  /// **'ابني 5 سنين بيرفض الصلاة، أعمل إيه؟'**
  String get chatQ_pray5;

  /// No description provided for @chatQ_tantrums.
  ///
  /// In ar, this message translates to:
  /// **'كيف أتعامل مع نوبات الغضب؟'**
  String get chatQ_tantrums;

  /// No description provided for @chatQ_screens.
  ///
  /// In ar, this message translates to:
  /// **'طفلي لا يترك التابلت والشاشات'**
  String get chatQ_screens;

  /// No description provided for @chatQ_study.
  ///
  /// In ar, this message translates to:
  /// **'طفلي لا يحب المذاكرة'**
  String get chatQ_study;

  /// No description provided for @chatQ_prayRegular.
  ///
  /// In ar, this message translates to:
  /// **'كيف أعوّد طفلي على الصلاة بانتظام؟'**
  String get chatQ_prayRegular;

  /// No description provided for @chatQ_lying.
  ///
  /// In ar, this message translates to:
  /// **'ابني يكذب أحيانًا — كيف أتصرف؟'**
  String get chatQ_lying;

  /// No description provided for @chatQ_gaming.
  ///
  /// In ar, this message translates to:
  /// **'ابني مشغول بالألعاب الإلكترونية طوال اليوم'**
  String get chatQ_gaming;

  /// No description provided for @chatQ_online.
  ///
  /// In ar, this message translates to:
  /// **'كيف أحمي طفلي على الإنترنت؟'**
  String get chatQ_online;

  /// No description provided for @chatQ_homework.
  ///
  /// In ar, this message translates to:
  /// **'ابني يماطل في واجباته المدرسية'**
  String get chatQ_homework;

  /// No description provided for @chatQ_teenDefiant.
  ///
  /// In ar, this message translates to:
  /// **'ابني المراهق يعاند ولا يسمع الكلام'**
  String get chatQ_teenDefiant;

  /// No description provided for @chatQ_socialMedia.
  ///
  /// In ar, this message translates to:
  /// **'ابنتي مشغولة بالسوشيال ميديا والمقارنات'**
  String get chatQ_socialMedia;

  /// No description provided for @chatQ_teenPray.
  ///
  /// In ar, this message translates to:
  /// **'كيف أحافظ على صلاة ابني المراهق؟'**
  String get chatQ_teenPray;

  /// No description provided for @chatQ_talkOlder.
  ///
  /// In ar, this message translates to:
  /// **'كيف أحاور ابني الكبير دون صدام؟'**
  String get chatQ_talkOlder;

  /// No description provided for @chatQ_university.
  ///
  /// In ar, this message translates to:
  /// **'ابني مقصّر في دراسته الجامعية'**
  String get chatQ_university;

  /// No description provided for @chatQ_friends.
  ///
  /// In ar, this message translates to:
  /// **'كيف أناقش ابني في اختيار أصحابه؟'**
  String get chatQ_friends;

  /// No description provided for @chatWelcome.
  ///
  /// In ar, this message translates to:
  /// **'مرحباً — اسأل عن أي تحدٍّ تربوي يواجهك'**
  String get chatWelcome;

  /// No description provided for @chatHint.
  ///
  /// In ar, this message translates to:
  /// **'اختر الفئة العمرية والشدة من الشريط أعلاه، ثم اكتب سؤالك.'**
  String get chatHint;

  /// No description provided for @chatMyChats.
  ///
  /// In ar, this message translates to:
  /// **'💬 محادثاتي'**
  String get chatMyChats;

  /// No description provided for @chatNewChat.
  ///
  /// In ar, this message translates to:
  /// **'محادثة جديدة'**
  String get chatNewChat;

  /// No description provided for @chatNoChats.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد محادثات سابقة بعد'**
  String get chatNoChats;

  /// No description provided for @chatAskAny.
  ///
  /// In ar, this message translates to:
  /// **'اسأل عن أي تحدٍّ تربوي'**
  String get chatAskAny;

  /// No description provided for @chatTypeQ.
  ///
  /// In ar, this message translates to:
  /// **'اكتب سؤالك…'**
  String get chatTypeQ;

  /// No description provided for @chatQuestion.
  ///
  /// In ar, this message translates to:
  /// **'سؤال'**
  String get chatQuestion;

  /// No description provided for @chatMessage.
  ///
  /// In ar, this message translates to:
  /// **'رسالة'**
  String get chatMessage;

  /// No description provided for @chatTurns.
  ///
  /// In ar, this message translates to:
  /// **'{count} سؤال'**
  String chatTurns(Object count);

  /// No description provided for @chatOfflineBanner.
  ///
  /// In ar, this message translates to:
  /// **'غير متصل بالإنترنت'**
  String get chatOfflineBanner;

  /// No description provided for @chatInit.
  ///
  /// In ar, this message translates to:
  /// **'جاري تهيئة الجلسة…'**
  String get chatInit;

  /// No description provided for @chatOfflineMsg.
  ///
  /// In ar, this message translates to:
  /// **'غير متصل — الأسئلة تحتاج اتصال بالإنترنت'**
  String get chatOfflineMsg;

  /// No description provided for @chatError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ. حاول مرة أخرى.'**
  String get chatError;

  /// No description provided for @chatTypeHint.
  ///
  /// In ar, this message translates to:
  /// **'اكتب سؤالك…'**
  String get chatTypeHint;

  /// No description provided for @chatBehaviorOptional.
  ///
  /// In ar, this message translates to:
  /// **'نوع السلوك (اختياري)'**
  String get chatBehaviorOptional;

  /// No description provided for @chatNewConfirmTitle.
  ///
  /// In ar, this message translates to:
  /// **'بدء محادثة جديدة؟'**
  String get chatNewConfirmTitle;

  /// No description provided for @chatNewConfirmDesc.
  ///
  /// In ar, this message translates to:
  /// **'سيتم إنهاء المحادثة الحالية وبدء جلسة جديدة على الخادم.'**
  String get chatNewConfirmDesc;

  /// No description provided for @chatCancel.
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get chatCancel;

  /// No description provided for @chatContinue.
  ///
  /// In ar, this message translates to:
  /// **'متابعة'**
  String get chatContinue;

  /// No description provided for @chatPrevChats.
  ///
  /// In ar, this message translates to:
  /// **'المحادثات السابقة'**
  String get chatPrevChats;

  /// No description provided for @chatTitle.
  ///
  /// In ar, this message translates to:
  /// **'🛡️  المربي الذكي'**
  String get chatTitle;

  /// No description provided for @chatTurnsCount.
  ///
  /// In ar, this message translates to:
  /// **'{count} سؤال'**
  String chatTurnsCount(Object count);

  /// No description provided for @chatNewConversation.
  ///
  /// In ar, this message translates to:
  /// **'بدء محادثة جديدة'**
  String get chatNewConversation;

  /// No description provided for @chatNoChatsYet.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد محادثات سابقة بعد'**
  String get chatNoChatsYet;

  /// No description provided for @chatNewChatBtn.
  ///
  /// In ar, this message translates to:
  /// **'محادثة جديدة'**
  String get chatNewChatBtn;

  /// No description provided for @chatSessionMessages.
  ///
  /// In ar, this message translates to:
  /// **'{count} رسالة'**
  String chatSessionMessages(Object count);

  /// No description provided for @chatEmptyWelcome.
  ///
  /// In ar, this message translates to:
  /// **'مرحباً — اسأل عن أي تحدٍّ تربوي يواجهك'**
  String get chatEmptyWelcome;

  /// No description provided for @chatEmptyHint.
  ///
  /// In ar, this message translates to:
  /// **'اختر الفئة العمرية والشدة من الشريط أعلاه، ثم اكتب سؤالك.'**
  String get chatEmptyHint;

  /// No description provided for @onbSelectAge.
  ///
  /// In ar, this message translates to:
  /// **'يجب اختيار المرحلة العمرية.'**
  String get onbSelectAge;

  /// No description provided for @onbServerSlow.
  ///
  /// In ar, this message translates to:
  /// **'الخادم يستغرق وقتاً أطول من المعتاد. تأكد من الاتصال وحاول مرة أخرى.'**
  String get onbServerSlow;

  /// No description provided for @onbChildError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إنشاء ملف الطفل: {error}'**
  String onbChildError(Object error);

  /// No description provided for @onbSaving.
  ///
  /// In ar, this message translates to:
  /// **'جاري الحفظ...'**
  String get onbSaving;

  /// No description provided for @onbStartJourney.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ الرحلة'**
  String get onbStartJourney;

  /// No description provided for @onbEditLater.
  ///
  /// In ar, this message translates to:
  /// **'يمكنك تعديل هذه المعلومات لاحقاً من الإعدادات.'**
  String get onbEditLater;

  /// No description provided for @onbPreparing.
  ///
  /// In ar, this message translates to:
  /// **'جاري تجهيز ملف طفلك…'**
  String get onbPreparing;

  /// No description provided for @onbWelcome.
  ///
  /// In ar, this message translates to:
  /// **'أهلاً بك 🌙'**
  String get onbWelcome;

  /// No description provided for @onbTagline1.
  ///
  /// In ar, this message translates to:
  /// **'«المربّي» رحلة تربية متكاملة ترافق طفلك خطوة بخطوة —'**
  String get onbTagline1;

  /// No description provided for @onbTagline2.
  ///
  /// In ar, this message translates to:
  /// **'ليست نصائح عابرة، بل منهجٌ تعيشه معه على مدى رحلته.'**
  String get onbTagline2;

  /// No description provided for @onbFreeTitle.
  ///
  /// In ar, this message translates to:
  /// **'🤍 مجاني بالكامل، لوجه الله'**
  String get onbFreeTitle;

  /// No description provided for @onbFreeDesc.
  ///
  /// In ar, this message translates to:
  /// **'بلا إعلانات ولا اشتراكات'**
  String get onbFreeDesc;

  /// No description provided for @onbFeature1Title.
  ///
  /// In ar, this message translates to:
  /// **'مسارات من ٢٨ يومًا'**
  String get onbFeature1Title;

  /// No description provided for @onbFeature1Desc.
  ///
  /// In ar, this message translates to:
  /// **'رحلات تربوية متدرّجة لكل مرحلة عمرية — تتابعها يومًا بيوم'**
  String get onbFeature1Desc;

  /// No description provided for @onbFeature2Title.
  ///
  /// In ar, this message translates to:
  /// **'دروس وبودكاست وفيديو'**
  String get onbFeature2Title;

  /// No description provided for @onbFeature2Desc.
  ///
  /// In ar, this message translates to:
  /// **'محتوى غني تعيشه بطرق متعددة، لا مجرد نصوص تُقرأ'**
  String get onbFeature2Desc;

  /// No description provided for @onbFeature3Title.
  ///
  /// In ar, this message translates to:
  /// **'رحلة طفلك'**
  String get onbFeature3Title;

  /// No description provided for @onbFeature3Desc.
  ///
  /// In ar, this message translates to:
  /// **'سجّل محطات نموّه الإيمانية وتابع تقدّمه عبر الزمن'**
  String get onbFeature3Desc;

  /// No description provided for @onbFeature4Title.
  ///
  /// In ar, this message translates to:
  /// **'مساعد ذكي'**
  String get onbFeature4Title;

  /// No description provided for @onbFeature4Desc.
  ///
  /// In ar, this message translates to:
  /// **'إجابات موثوقة عن تحدياتك التربوية وقت ما تحتاج'**
  String get onbFeature4Desc;

  /// No description provided for @onbMoreThanReading.
  ///
  /// In ar, this message translates to:
  /// **'أكثر من مجرد قراءة'**
  String get onbMoreThanReading;

  /// No description provided for @onbCurriculumDesc.
  ///
  /// In ar, this message translates to:
  /// **'منهجٌ تربوي متكامل تعيشه مع طفلك خطوة بخطوة — لا تقرؤه في دقائق:'**
  String get onbCurriculumDesc;

  /// No description provided for @onbTellUs.
  ///
  /// In ar, this message translates to:
  /// **'حدّثنا عن طفلك'**
  String get onbTellUs;

  /// No description provided for @onbPersonalize.
  ///
  /// In ar, this message translates to:
  /// **'لنخصّص له تجربة تربوية مناسبة.'**
  String get onbPersonalize;

  /// No description provided for @onbChildName.
  ///
  /// In ar, this message translates to:
  /// **'اسم طفلك'**
  String get onbChildName;

  /// No description provided for @onbNameHint.
  ///
  /// In ar, this message translates to:
  /// **'مثلاً: سارة، أحمد، ليلى'**
  String get onbNameHint;

  /// No description provided for @onbNameRequired.
  ///
  /// In ar, this message translates to:
  /// **'الاسم مطلوب'**
  String get onbNameRequired;

  /// No description provided for @onbNameTooLong.
  ///
  /// In ar, this message translates to:
  /// **'الاسم طويل جداً (الحد الأقصى 80 حرفاً)'**
  String get onbNameTooLong;

  /// No description provided for @onbAgeGroup.
  ///
  /// In ar, this message translates to:
  /// **'المرحلة العمرية'**
  String get onbAgeGroup;

  /// No description provided for @onbChildAvatar.
  ///
  /// In ar, this message translates to:
  /// **'صورة الطفل (اختياري)'**
  String get onbChildAvatar;

  /// No description provided for @onbTapEmoji.
  ///
  /// In ar, this message translates to:
  /// **'اضغط لاختيار إيموجي'**
  String get onbTapEmoji;

  /// No description provided for @onbTapChangeEmoji.
  ///
  /// In ar, this message translates to:
  /// **'اضغط لتغيير الإيموجي'**
  String get onbTapChangeEmoji;

  /// No description provided for @onbGender.
  ///
  /// In ar, this message translates to:
  /// **'الجنس (اختياري)'**
  String get onbGender;

  /// No description provided for @onbBoy.
  ///
  /// In ar, this message translates to:
  /// **'ولد'**
  String get onbBoy;

  /// No description provided for @onbGirl.
  ///
  /// In ar, this message translates to:
  /// **'بنت'**
  String get onbGirl;

  /// No description provided for @onbClear.
  ///
  /// In ar, this message translates to:
  /// **'مسح'**
  String get onbClear;

  /// No description provided for @quranDailyWird.
  ///
  /// In ar, this message translates to:
  /// **'الورد اليومي'**
  String get quranDailyWird;

  /// No description provided for @quranCompleteReading.
  ///
  /// In ar, this message translates to:
  /// **'إكمال القراءة'**
  String get quranCompleteReading;

  /// No description provided for @quranSurahVerse.
  ///
  /// In ar, this message translates to:
  /// **'سورة {surah} - آية {verse}'**
  String quranSurahVerse(Object surah, Object verse);

  /// No description provided for @quranVerseCount.
  ///
  /// In ar, this message translates to:
  /// **'آياتها: {count}'**
  String quranVerseCount(Object count);

  /// No description provided for @quranLoadError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ أثناء تحميل المصحف: {error}'**
  String quranLoadError(Object error);

  /// No description provided for @quranChooseReciter.
  ///
  /// In ar, this message translates to:
  /// **'اختر القارئ'**
  String get quranChooseReciter;

  /// No description provided for @quranPlayError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تشغيل التلاوة. تأكد من اتصالك بالإنترنت.'**
  String get quranPlayError;

  /// No description provided for @quranReciter.
  ///
  /// In ar, this message translates to:
  /// **'القارئ'**
  String get quranReciter;

  /// No description provided for @quranStopRecitation.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف التلاوة'**
  String get quranStopRecitation;

  /// No description provided for @quranListen.
  ///
  /// In ar, this message translates to:
  /// **'استماع'**
  String get quranListen;

  /// No description provided for @quranLoading.
  ///
  /// In ar, this message translates to:
  /// **'جاري التحميل...'**
  String get quranLoading;

  /// No description provided for @quranDailyComplete.
  ///
  /// In ar, this message translates to:
  /// **'أكملت ورد اليوم، بارك الله فيك!'**
  String get quranDailyComplete;

  /// No description provided for @quranDailyProgress.
  ///
  /// In ar, this message translates to:
  /// **'ورد اليوم: {current} / {total} آيات'**
  String quranDailyProgress(Object current, Object total);

  /// No description provided for @quranNextSurah.
  ///
  /// In ar, this message translates to:
  /// **'السورة التالية'**
  String get quranNextSurah;

  /// No description provided for @quranPrevSurah.
  ///
  /// In ar, this message translates to:
  /// **'السورة السابقة'**
  String get quranPrevSurah;

  /// No description provided for @quranStop.
  ///
  /// In ar, this message translates to:
  /// **'إيقاف'**
  String get quranStop;

  /// No description provided for @quranBismillah.
  ///
  /// In ar, this message translates to:
  /// **'بِسۡمِ ٱللَّهِ ٱلرَّحۡمَٰنِ ٱلرَّحِيمِ'**
  String get quranBismillah;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
