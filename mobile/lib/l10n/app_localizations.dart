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

  /// No description provided for @navLearn.
  ///
  /// In ar, this message translates to:
  /// **'التعلّم'**
  String get navLearn;

  /// No description provided for @navMore.
  ///
  /// In ar, this message translates to:
  /// **'المزيد'**
  String get navMore;

  /// No description provided for @hubTitle.
  ///
  /// In ar, this message translates to:
  /// **'المزيد'**
  String get hubTitle;

  /// No description provided for @hubGroupChild.
  ///
  /// In ar, this message translates to:
  /// **'طفلي'**
  String get hubGroupChild;

  /// No description provided for @hubGroupAchievements.
  ///
  /// In ar, this message translates to:
  /// **'الإنجازات'**
  String get hubGroupAchievements;

  /// No description provided for @hubGroupLibrary.
  ///
  /// In ar, this message translates to:
  /// **'المكتبة'**
  String get hubGroupLibrary;

  /// No description provided for @hubGroupGames.
  ///
  /// In ar, this message translates to:
  /// **'الألعاب'**
  String get hubGroupGames;

  /// No description provided for @hubGroupHelp.
  ///
  /// In ar, this message translates to:
  /// **'الإعدادات والمساعدة'**
  String get hubGroupHelp;

  /// No description provided for @hubMyChildren.
  ///
  /// In ar, this message translates to:
  /// **'أطفالي'**
  String get hubMyChildren;

  /// No description provided for @hubCustomizeHabits.
  ///
  /// In ar, this message translates to:
  /// **'تخصيص العادات'**
  String get hubCustomizeHabits;

  /// No description provided for @hubInsights.
  ///
  /// In ar, this message translates to:
  /// **'رؤى تربوية'**
  String get hubInsights;

  /// No description provided for @hubCreateStory.
  ///
  /// In ar, this message translates to:
  /// **'اصنع قصة'**
  String get hubCreateStory;

  /// No description provided for @hubAccount.
  ///
  /// In ar, this message translates to:
  /// **'حسابي'**
  String get hubAccount;

  /// No description provided for @helpTitle.
  ///
  /// In ar, this message translates to:
  /// **'أين أجد…؟'**
  String get helpTitle;

  /// No description provided for @helpSubtitle.
  ///
  /// In ar, this message translates to:
  /// **'اضغط على سؤالك ونوصّلك فورًا'**
  String get helpSubtitle;

  /// No description provided for @helpWhereGames.
  ///
  /// In ar, this message translates to:
  /// **'أين ألعاب طفلي؟'**
  String get helpWhereGames;

  /// No description provided for @helpWhereStories.
  ///
  /// In ar, this message translates to:
  /// **'أين قصص ما قبل النوم؟'**
  String get helpWhereStories;

  /// No description provided for @helpHowAddChild.
  ///
  /// In ar, this message translates to:
  /// **'كيف أضيف طفلًا آخر؟'**
  String get helpHowAddChild;

  /// No description provided for @helpWhereQuran.
  ///
  /// In ar, this message translates to:
  /// **'أين الورد والقرآن؟'**
  String get helpWhereQuran;

  /// No description provided for @helpWhereProgress.
  ///
  /// In ar, this message translates to:
  /// **'أين متابعة يوم طفلي؟'**
  String get helpWhereProgress;

  /// No description provided for @helpWhereBadges.
  ///
  /// In ar, this message translates to:
  /// **'أين الشعارات والإنجازات؟'**
  String get helpWhereBadges;

  /// No description provided for @helpHowBackup.
  ///
  /// In ar, this message translates to:
  /// **'كيف أحفظ تقدمي؟'**
  String get helpHowBackup;

  /// No description provided for @helpHowContact.
  ///
  /// In ar, this message translates to:
  /// **'كيف أراسلكم؟'**
  String get helpHowContact;

  /// No description provided for @helpTooltip.
  ///
  /// In ar, this message translates to:
  /// **'مساعدة'**
  String get helpTooltip;

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
  /// **'بطل العادات الذكية'**
  String get healthyHero;

  /// No description provided for @treeOfDeeds.
  ///
  /// In ar, this message translates to:
  /// **'شجرة الأخلاق'**
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

  /// No description provided for @startThisLesson.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ هذا الدرس'**
  String get startThisLesson;

  /// No description provided for @startFirstLessonDesc.
  ///
  /// In ar, this message translates to:
  /// **'درس قصير مختار لعمر طفلك — يبدأ من هنا.'**
  String get startFirstLessonDesc;

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

  /// No description provided for @chatQ_fears.
  ///
  /// In ar, this message translates to:
  /// **'طفلي كثير الخوف — من الظلام أو النوم وحده'**
  String get chatQ_fears;

  /// No description provided for @chatQ_siblings.
  ///
  /// In ar, this message translates to:
  /// **'ابني يغار من أخيه الصغير ويؤذيه'**
  String get chatQ_siblings;

  /// No description provided for @chatQ_bodyChanges.
  ///
  /// In ar, this message translates to:
  /// **'كيف أتحدث مع طفلي عن التغيرات الجسدية والخصوصية؟'**
  String get chatQ_bodyChanges;

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

  /// No description provided for @onbAgeQuestion.
  ///
  /// In ar, this message translates to:
  /// **'كم عمر طفلك؟'**
  String get onbAgeQuestion;

  /// No description provided for @onbAgeQuestionSub.
  ///
  /// In ar, this message translates to:
  /// **'سؤال واحد فقط — ونجهّز لك تجربة مخصّصة فورًا.'**
  String get onbAgeQuestionSub;

  /// No description provided for @onbFirstTipTitle.
  ///
  /// In ar, this message translates to:
  /// **'أول نصيحة مخصّصة لك 🎁'**
  String get onbFirstTipTitle;

  /// No description provided for @onbTipForAge.
  ///
  /// In ar, this message translates to:
  /// **'لمرحلة {ageLabel}'**
  String onbTipForAge(String ageLabel);

  /// No description provided for @onbTip_prenatal.
  ///
  /// In ar, this message translates to:
  /// **'صوتك أول مدرسة لطفلك: اجعل الأذكار والقرآن خلفية هادئة ليومه — فالسكينة التي يسمعها اليوم تصير أمانه غدًا.'**
  String get onbTip_prenatal;

  /// No description provided for @onbTip_2to3.
  ///
  /// In ar, this message translates to:
  /// **'في هذا العمر «لا» ليست عنادًا بل اكتشاف للذات. أعطِ طفلك خيارين كلاهما مقبول لك — يشعر هو بالتحكم، وتصل أنت لما تريد.'**
  String get onbTip_2to3;

  /// No description provided for @onbTip_4to6.
  ///
  /// In ar, this message translates to:
  /// **'حبّب طفلك في الصلاة قبل أن تطالبه بها: دعه يفرش سجادته بجوارك ويقلّدك بلا أوامر — القدوة في هذا العمر أقوى من مئة تعليمة.'**
  String get onbTip_4to6;

  /// No description provided for @onbTip_7to9.
  ///
  /// In ar, this message translates to:
  /// **'هذا عمر «مُروا أولادكم بالصلاة» — ابدأ بالتشجيع لا بالعقاب، وثبّتا معًا صلاة واحدة يوميًا قبل أن تطلب الخمس.'**
  String get onbTip_7to9;

  /// No description provided for @onbTip_10to12.
  ///
  /// In ar, this message translates to:
  /// **'هذه سنوات بناء الثقة قبل المراهقة: خصّص 10 دقائق يوميًا تسمع فيها طفلك دون مقاطعة ولا نصائح — من يجد أذنًا في البيت لا يبحث عنها خارجه.'**
  String get onbTip_10to12;

  /// No description provided for @onbTip_13to15.
  ///
  /// In ar, this message translates to:
  /// **'المراهق لا يسمع المحاضرات لكنه يراقب الأفعال. عامله كشريك: اطلب رأيه وناقشه بدل أن تأمره — الاحترام يفتح ما تغلقه الأوامر.'**
  String get onbTip_13to15;

  /// No description provided for @onbTip_16to18.
  ///
  /// In ar, this message translates to:
  /// **'ابنك على أعتاب الاستقلال: انتقل من دور «الرقيب» إلى دور «المستشار»، وابدأ قراراته المصيرية بسؤال «ما رأيك؟» قبل «افعل».'**
  String get onbTip_16to18;

  /// No description provided for @onbReadyForYou.
  ///
  /// In ar, this message translates to:
  /// **'وفي انتظارك داخل التطبيق:'**
  String get onbReadyForYou;

  /// No description provided for @onbReadyPath.
  ///
  /// In ar, this message translates to:
  /// **'مسار تربوي متدرّج مخصّص لهذه المرحلة'**
  String get onbReadyPath;

  /// No description provided for @onbReadyChat.
  ///
  /// In ar, this message translates to:
  /// **'مرشد ذكي يجيب عن أسئلتك، مثل:'**
  String get onbReadyChat;

  /// No description provided for @onbDefaultChildName.
  ///
  /// In ar, this message translates to:
  /// **'طفلي'**
  String get onbDefaultChildName;

  /// No description provided for @onbDeferredHint.
  ///
  /// In ar, this message translates to:
  /// **'يمكنك إضافة اسم طفلك وصورته لاحقًا من الإعدادات.'**
  String get onbDeferredHint;

  /// No description provided for @onbChangeAge.
  ///
  /// In ar, this message translates to:
  /// **'تغيير العمر'**
  String get onbChangeAge;

  /// No description provided for @prideStreakTitle.
  ///
  /// In ar, this message translates to:
  /// **'ما شاء الله — {days} أيام متواصلة! 🔥'**
  String prideStreakTitle(int days);

  /// No description provided for @prideStreakBody.
  ///
  /// In ar, this message translates to:
  /// **'استمراركم هذا نعمة تستحق أن تُشارك. هل تعرف أسرة تتمنى لها نفس الخير؟ الدلالة على الخير صدقة جارية.'**
  String get prideStreakBody;

  /// No description provided for @prideInviteCta.
  ///
  /// In ar, this message translates to:
  /// **'ادعُ صديقًا'**
  String get prideInviteCta;

  /// No description provided for @prideLater.
  ///
  /// In ar, this message translates to:
  /// **'لاحقًا'**
  String get prideLater;

  /// No description provided for @prideStoryInvite.
  ///
  /// In ar, this message translates to:
  /// **'أسعدت طفلك القصة؟ دلّ أسرة أخرى عليها 🤍'**
  String get prideStoryInvite;

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

  /// No description provided for @routineTitle.
  ///
  /// In ar, this message translates to:
  /// **'ميزان العادات'**
  String get routineTitle;

  /// No description provided for @routineDailyTracker.
  ///
  /// In ar, this message translates to:
  /// **'حساب اليوم'**
  String get routineDailyTracker;

  /// No description provided for @routineNewEvent.
  ///
  /// In ar, this message translates to:
  /// **'حدث جديد'**
  String get routineNewEvent;

  /// No description provided for @routineUnder9.
  ///
  /// In ar, this message translates to:
  /// **'التتبع اليومي متاح للأطفال حتى 9 سنوات'**
  String get routineUnder9;

  /// No description provided for @routineAddChildFirst.
  ///
  /// In ar, this message translates to:
  /// **'أضف طفلك أولاً من شاشة اليوم'**
  String get routineAddChildFirst;

  /// No description provided for @routineSummary.
  ///
  /// In ar, this message translates to:
  /// **'ملخّص {days} أيام'**
  String routineSummary(Object days);

  /// No description provided for @routineSleep.
  ///
  /// In ar, this message translates to:
  /// **'نوم'**
  String get routineSleep;

  /// No description provided for @routineFeeds.
  ///
  /// In ar, this message translates to:
  /// **'رضاعات'**
  String get routineFeeds;

  /// No description provided for @routineDiapers.
  ///
  /// In ar, this message translates to:
  /// **'حاضات'**
  String get routineDiapers;

  /// No description provided for @routineNoEvents.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد أحداث اليوم'**
  String get routineNoEvents;

  /// No description provided for @routineTapPlus.
  ///
  /// In ar, this message translates to:
  /// **'اضغط + لإضافة أول حدث'**
  String get routineTapPlus;

  /// No description provided for @routineDeleteConfirm.
  ///
  /// In ar, this message translates to:
  /// **'حذف الحدث؟'**
  String get routineDeleteConfirm;

  /// No description provided for @routineCancel.
  ///
  /// In ar, this message translates to:
  /// **'إلغاء'**
  String get routineCancel;

  /// No description provided for @routineDelete.
  ///
  /// In ar, this message translates to:
  /// **'حذف'**
  String get routineDelete;

  /// No description provided for @routineAddEvent.
  ///
  /// In ar, this message translates to:
  /// **'إضافة حدث {type}'**
  String routineAddEvent(Object type);

  /// No description provided for @routineNoteOptional.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظة (اختياري)'**
  String get routineNoteOptional;

  /// No description provided for @routineNoMedNote.
  ///
  /// In ar, this message translates to:
  /// **'لا تكتب أدوية أو أعراض طبية'**
  String get routineNoMedNote;

  /// No description provided for @routineSave.
  ///
  /// In ar, this message translates to:
  /// **'حفظ'**
  String get routineSave;

  /// No description provided for @routineBreast.
  ///
  /// In ar, this message translates to:
  /// **'ثدي'**
  String get routineBreast;

  /// No description provided for @routineBottle.
  ///
  /// In ar, this message translates to:
  /// **'رضّاعة'**
  String get routineBottle;

  /// No description provided for @routineSolidFood.
  ///
  /// In ar, this message translates to:
  /// **'طعام صلب'**
  String get routineSolidFood;

  /// No description provided for @routineLeft.
  ///
  /// In ar, this message translates to:
  /// **'يسار'**
  String get routineLeft;

  /// No description provided for @routineRight.
  ///
  /// In ar, this message translates to:
  /// **'يمين'**
  String get routineRight;

  /// No description provided for @routineBoth.
  ///
  /// In ar, this message translates to:
  /// **'كلاهما'**
  String get routineBoth;

  /// No description provided for @routineQuantityMl.
  ///
  /// In ar, this message translates to:
  /// **'الكمية تقريباً (ml)'**
  String get routineQuantityMl;

  /// No description provided for @routineWet.
  ///
  /// In ar, this message translates to:
  /// **'بلل'**
  String get routineWet;

  /// No description provided for @routineSolid.
  ///
  /// In ar, this message translates to:
  /// **'براز'**
  String get routineSolid;

  /// No description provided for @routineEndTime.
  ///
  /// In ar, this message translates to:
  /// **'النهاية:'**
  String get routineEndTime;

  /// No description provided for @routineWakeTime.
  ///
  /// In ar, this message translates to:
  /// **'اختر وقت الاستيقاظ'**
  String get routineWakeTime;

  /// No description provided for @routineMedicalWarning.
  ///
  /// In ar, this message translates to:
  /// **'الملاحظة تحتوي على مصطلح طبي/دواء. رجاءً اكتب ملاحظة روتينية فقط.'**
  String get routineMedicalWarning;

  /// No description provided for @routineError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ'**
  String get routineError;

  /// No description provided for @routineQrError.
  ///
  /// In ar, this message translates to:
  /// **'تعذر إنشاء رمز QR: {error}'**
  String routineQrError(Object error);

  /// No description provided for @routineShareBalance.
  ///
  /// In ar, this message translates to:
  /// **'شارك الميزان مع المراهق'**
  String get routineShareBalance;

  /// No description provided for @routineQrInstructions.
  ///
  /// In ar, this message translates to:
  /// **'امسح الرمز من هاتف الابن، أو انسخ الرابط وأرسله عبر واتساب.'**
  String get routineQrInstructions;

  /// No description provided for @routineClose.
  ///
  /// In ar, this message translates to:
  /// **'إغلاق'**
  String get routineClose;

  /// No description provided for @routineLinkCopied.
  ///
  /// In ar, this message translates to:
  /// **'تم نسخ الرابط'**
  String get routineLinkCopied;

  /// No description provided for @routineCopyLink.
  ///
  /// In ar, this message translates to:
  /// **'نسخ الرابط'**
  String get routineCopyLink;

  /// No description provided for @routineCustomize.
  ///
  /// In ar, this message translates to:
  /// **'تخصيص العادات'**
  String get routineCustomize;

  /// No description provided for @routineChild.
  ///
  /// In ar, this message translates to:
  /// **'الطفل'**
  String get routineChild;

  /// No description provided for @routineShareWeb.
  ///
  /// In ar, this message translates to:
  /// **'مشاركة الميزان عبر الويب 🔗'**
  String get routineShareWeb;

  /// No description provided for @routineChildMode.
  ///
  /// In ar, this message translates to:
  /// **'تسليم الجهاز للطفل (وضع الطفل)'**
  String get routineChildMode;

  /// No description provided for @routineTodayPoints.
  ///
  /// In ar, this message translates to:
  /// **'نقاط اليوم'**
  String get routineTodayPoints;

  /// No description provided for @routineNoHabits.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد عادات في هذا القسم'**
  String get routineNoHabits;

  /// No description provided for @routineRecordFailed.
  ///
  /// In ar, this message translates to:
  /// **'فشل التسجيل: {error}'**
  String routineRecordFailed(Object error);

  /// No description provided for @routineDeleteFailed.
  ///
  /// In ar, this message translates to:
  /// **'فشل الحذف: {error}'**
  String routineDeleteFailed(Object error);

  /// No description provided for @settingsMediaLangChanged.
  ///
  /// In ar, this message translates to:
  /// **'تم تغيير لغة الوسائط إلى العربية'**
  String get settingsMediaLangChanged;

  /// No description provided for @settingsTitle.
  ///
  /// In ar, this message translates to:
  /// **'الإعدادات'**
  String get settingsTitle;

  /// No description provided for @settingsNoChild.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد ملف طفل نشط.'**
  String get settingsNoChild;

  /// No description provided for @settingsSwitchChild.
  ///
  /// In ar, this message translates to:
  /// **'تبديل الطفل النشط'**
  String get settingsSwitchChild;

  /// No description provided for @settingsChildCount.
  ///
  /// In ar, this message translates to:
  /// **'لديك {count} من أصل {max} أطفال'**
  String settingsChildCount(Object count, Object max);

  /// No description provided for @settingsEditChild.
  ///
  /// In ar, this message translates to:
  /// **'تعديل معلومات الطفل'**
  String get settingsEditChild;

  /// No description provided for @settingsEditChildDesc.
  ///
  /// In ar, this message translates to:
  /// **'الاسم، المرحلة العمرية، الصورة، الجنس'**
  String get settingsEditChildDesc;

  /// No description provided for @settingsInviteFriend.
  ///
  /// In ar, this message translates to:
  /// **'ادعُ صديقاً 🤍'**
  String get settingsInviteFriend;

  /// No description provided for @settingsInviteDesc.
  ///
  /// In ar, this message translates to:
  /// **'دلالتك على الخير صدقة — وكلاكما يكسب مكافأة'**
  String get settingsInviteDesc;

  /// No description provided for @settingsBackup.
  ///
  /// In ar, this message translates to:
  /// **'احفظ تقدمك 🤍'**
  String get settingsBackup;

  /// No description provided for @settingsBackupDesc.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل دخول اختياري — يحفظ بياناتك لو غيّرت الجهاز'**
  String get settingsBackupDesc;

  /// No description provided for @settingsShareFeedback.
  ///
  /// In ar, this message translates to:
  /// **'شاركنا رأيك'**
  String get settingsShareFeedback;

  /// No description provided for @settingsShareFeedbackDesc.
  ///
  /// In ar, this message translates to:
  /// **'اقتراح أو مشكلة — كتابةً أو صوتاً، يصل لنا مباشرة'**
  String get settingsShareFeedbackDesc;

  /// No description provided for @settingsResetProgress.
  ///
  /// In ar, this message translates to:
  /// **'إعادة تعيين التقدم'**
  String get settingsResetProgress;

  /// No description provided for @settingsResetDesc.
  ///
  /// In ar, this message translates to:
  /// **'سيتم مسح كل الدروس المكمّلة وإعادة السلسلة إلى 0'**
  String get settingsResetDesc;

  /// No description provided for @settingsMediaLang.
  ///
  /// In ar, this message translates to:
  /// **'لغة الوسائط التعليمية'**
  String get settingsMediaLang;

  /// No description provided for @settingsArabicMedia.
  ///
  /// In ar, this message translates to:
  /// **'العربية (بودكاست وفيديو عربي)'**
  String get settingsArabicMedia;

  /// No description provided for @settingsRate.
  ///
  /// In ar, this message translates to:
  /// **'قيّم التطبيق'**
  String get settingsRate;

  /// No description provided for @settingsRateDesc.
  ///
  /// In ar, this message translates to:
  /// **'رأيك يساعد آباءً غيرك يجدون «المربّي»'**
  String get settingsRateDesc;

  /// No description provided for @settingsPrivacy.
  ///
  /// In ar, this message translates to:
  /// **'سياسة الخصوصية'**
  String get settingsPrivacy;

  /// No description provided for @settingsPrivacyDesc.
  ///
  /// In ar, this message translates to:
  /// **'كيف نتعامل مع بياناتك'**
  String get settingsPrivacyDesc;

  /// No description provided for @settingsFavorites.
  ///
  /// In ar, this message translates to:
  /// **'المفضلة'**
  String get settingsFavorites;

  /// No description provided for @settingsFavoritesDesc.
  ///
  /// In ar, this message translates to:
  /// **'الدروس والنصائح التي حفظتها'**
  String get settingsFavoritesDesc;

  /// No description provided for @settingsAchievements.
  ///
  /// In ar, this message translates to:
  /// **'إنجازاتي'**
  String get settingsAchievements;

  /// No description provided for @settingsAchievementsDesc.
  ///
  /// In ar, this message translates to:
  /// **'الشعارات التي حصلت عليها'**
  String get settingsAchievementsDesc;

  /// No description provided for @settingsExport.
  ///
  /// In ar, this message translates to:
  /// **'تصدير بياناتي'**
  String get settingsExport;

  /// No description provided for @settingsExportDesc.
  ///
  /// In ar, this message translates to:
  /// **'تصدير المفضلة والملاحظات كملف JSON'**
  String get settingsExportDesc;

  /// No description provided for @settingsImport.
  ///
  /// In ar, this message translates to:
  /// **'استيراد بياناتي'**
  String get settingsImport;

  /// No description provided for @settingsImportDesc.
  ///
  /// In ar, this message translates to:
  /// **'استيراد النسخة الاحتياطية من ملف JSON'**
  String get settingsImportDesc;

  /// No description provided for @settingsVersion.
  ///
  /// In ar, this message translates to:
  /// **'الإصدار {version}'**
  String settingsVersion(Object version);

  /// No description provided for @settingsPreparingBackup.
  ///
  /// In ar, this message translates to:
  /// **'جاري تجهيز النسخة الاحتياطية...'**
  String get settingsPreparingBackup;

  /// No description provided for @settingsBackupTitle.
  ///
  /// In ar, this message translates to:
  /// **'نسخة احتياطية من بيانات المربي الذكي'**
  String get settingsBackupTitle;

  /// No description provided for @settingsBackupName.
  ///
  /// In ar, this message translates to:
  /// **'نسخة احتياطية - المربي الذكي'**
  String get settingsBackupName;

  /// No description provided for @settingsExportSuccess.
  ///
  /// In ar, this message translates to:
  /// **'تم تصدير البيانات بنجاح'**
  String get settingsExportSuccess;

  /// No description provided for @settingsExportFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر التصدير: {error}'**
  String settingsExportFailed(Object error);

  /// No description provided for @settingsImportFile.
  ///
  /// In ar, this message translates to:
  /// **'اختر ملف النسخة الاحتياطية'**
  String get settingsImportFile;

  /// No description provided for @settingsImportConfirm.
  ///
  /// In ar, this message translates to:
  /// **'استيراد البيانات؟'**
  String get settingsImportConfirm;

  /// No description provided for @settingsImportDesc1.
  ///
  /// In ar, this message translates to:
  /// **'سيتم دمج البيانات المستوردة مع بياناتك الحالية.'**
  String get settingsImportDesc1;

  /// No description provided for @settingsImportDesc2.
  ///
  /// In ar, this message translates to:
  /// **'هذا الإجراء لا يمكن التراجع عنه بسهولة.'**
  String get settingsImportDesc2;

  /// No description provided for @settingsImportBtn.
  ///
  /// In ar, this message translates to:
  /// **'استيراد'**
  String get settingsImportBtn;

  /// No description provided for @settingsImporting.
  ///
  /// In ar, this message translates to:
  /// **'جاري استيراد البيانات...'**
  String get settingsImporting;

  /// No description provided for @settingsImportSuccess.
  ///
  /// In ar, this message translates to:
  /// **'تم الاستيراد بنجاح: {reflections} ملاحظة، {favorites} مفضلة'**
  String settingsImportSuccess(Object favorites, Object reflections);

  /// No description provided for @settingsImportFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الاستيراد: {error}'**
  String settingsImportFailed(Object error);

  /// No description provided for @settingsResetConfirm.
  ///
  /// In ar, this message translates to:
  /// **'إعادة تعيين التقدم؟'**
  String get settingsResetConfirm;

  /// No description provided for @settingsResetDesc1.
  ///
  /// In ar, this message translates to:
  /// **'سيتم مسح كل الدروس المكمّلة لـ {name} وستُعاد السلسلة إلى الصفر.'**
  String settingsResetDesc1(Object name);

  /// No description provided for @settingsResetDesc2.
  ///
  /// In ar, this message translates to:
  /// **'هذا الإجراء لا يمكن التراجع عنه.'**
  String get settingsResetDesc2;

  /// No description provided for @settingsResetBtn.
  ///
  /// In ar, this message translates to:
  /// **'إعادة التعيين'**
  String get settingsResetBtn;

  /// No description provided for @settingsNoProgress.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد تقدم لإعادة تعيينه.'**
  String get settingsNoProgress;

  /// No description provided for @settingsResetDone.
  ///
  /// In ar, this message translates to:
  /// **'تم مسح {count} درس. السلسلة الآن 0.'**
  String settingsResetDone(Object count);

  /// No description provided for @settingsResetFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إعادة التعيين: {error}'**
  String settingsResetFailed(Object error);

  /// No description provided for @settingsFamilyAdhkar.
  ///
  /// In ar, this message translates to:
  /// **'إشعارات أذكار الأسرة'**
  String get settingsFamilyAdhkar;

  /// No description provided for @settingsFamilyAdhkarDesc.
  ///
  /// In ar, this message translates to:
  /// **'آية أو حديث أو نصيحة — مرة واحدة كل صباح'**
  String get settingsFamilyAdhkarDesc;

  /// No description provided for @settingsEnglishMedia.
  ///
  /// In ar, this message translates to:
  /// **'الإنجليزية (بودكاست وفيديو بالإنجليزية)'**
  String get settingsEnglishMedia;

  /// No description provided for @settingsMediaLangChangedEn.
  ///
  /// In ar, this message translates to:
  /// **'تم تغيير لغة الوسائط إلى الإنجليزية'**
  String get settingsMediaLangChangedEn;

  /// No description provided for @settingsLoadFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الإعدادات.\n{error}'**
  String settingsLoadFailed(Object error);

  /// No description provided for @settingsMethodologyLink.
  ///
  /// In ar, this message translates to:
  /// **'منهجيتنا ومصادرنا'**
  String get settingsMethodologyLink;

  /// No description provided for @settingsMethodologyDesc.
  ///
  /// In ar, this message translates to:
  /// **'كيف نختار المحتوى ومصادره العلمية والشرعية'**
  String get settingsMethodologyDesc;

  /// No description provided for @settingsFollowUs.
  ///
  /// In ar, this message translates to:
  /// **'تابعنا'**
  String get settingsFollowUs;

  /// No description provided for @settingsFollowUsDesc.
  ///
  /// In ar, this message translates to:
  /// **'نصائح ومقاطع قصيرة أول بأول على صفحاتنا'**
  String get settingsFollowUsDesc;

  /// No description provided for @genderOther.
  ///
  /// In ar, this message translates to:
  /// **'أخرى'**
  String get genderOther;

  /// No description provided for @lessonTitle.
  ///
  /// In ar, this message translates to:
  /// **'الدرس'**
  String get lessonTitle;

  /// No description provided for @lessonCompleted.
  ///
  /// In ar, this message translates to:
  /// **'مكتمل ✓'**
  String get lessonCompleted;

  /// No description provided for @lessonMarking.
  ///
  /// In ar, this message translates to:
  /// **'جارٍ التسجيل…'**
  String get lessonMarking;

  /// No description provided for @lessonMarkComplete.
  ///
  /// In ar, this message translates to:
  /// **'أتممت هذا الدرس'**
  String get lessonMarkComplete;

  /// No description provided for @lessonSummary.
  ///
  /// In ar, this message translates to:
  /// **'ملخص الدرس'**
  String get lessonSummary;

  /// No description provided for @lessonTryThis.
  ///
  /// In ar, this message translates to:
  /// **'جرّب هذا'**
  String get lessonTryThis;

  /// No description provided for @lessonReflections.
  ///
  /// In ar, this message translates to:
  /// **'أسئلة للتأمل'**
  String get lessonReflections;

  /// No description provided for @lessonUnitRefs.
  ///
  /// In ar, this message translates to:
  /// **'مرتبط بـ {count} وحدات من قاعدة المعرفة'**
  String lessonUnitRefs(Object count);

  /// No description provided for @lessonWarningFollowup.
  ///
  /// In ar, this message translates to:
  /// **'هذا الدرس يحتوي على توجيهات تستحق المتابعة مع متخصص. لا تتردد في استشارة طبيب أو أخصائي تنموي إذا شعرت بالحاجة.'**
  String get lessonWarningFollowup;

  /// No description provided for @lessonErrorLoading.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الدرس'**
  String get lessonErrorLoading;

  /// No description provided for @lessonErrorMarking.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تسجيل الإكمال: {error}'**
  String lessonErrorMarking(Object error);

  /// No description provided for @lessonCelebrationTitle.
  ///
  /// In ar, this message translates to:
  /// **'ما شاء الله!'**
  String get lessonCelebrationTitle;

  /// No description provided for @lessonCelebrationMsg.
  ///
  /// In ar, this message translates to:
  /// **'تم تسجيل إكمال الدرس'**
  String get lessonCelebrationMsg;

  /// No description provided for @lessonFavAdd.
  ///
  /// In ar, this message translates to:
  /// **'إضافة للمفضلة'**
  String get lessonFavAdd;

  /// No description provided for @lessonFavRemove.
  ///
  /// In ar, this message translates to:
  /// **'إزالة من المفضلة'**
  String get lessonFavRemove;

  /// No description provided for @lessonStatusCompleted.
  ///
  /// In ar, this message translates to:
  /// **'مكتمل'**
  String get lessonStatusCompleted;

  /// No description provided for @lessonStatusInProgress.
  ///
  /// In ar, this message translates to:
  /// **'قيد التنفيذ'**
  String get lessonStatusInProgress;

  /// No description provided for @lessonStatusNotStarted.
  ///
  /// In ar, this message translates to:
  /// **'لم يبدأ بعد'**
  String get lessonStatusNotStarted;

  /// No description provided for @lessonStartInteractive.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ بالمحتوى التفاعلي'**
  String get lessonStartInteractive;

  /// No description provided for @lessonListenPodcast.
  ///
  /// In ar, this message translates to:
  /// **'🎧 استمع للبودكاست'**
  String get lessonListenPodcast;

  /// No description provided for @lessonWatchVideo.
  ///
  /// In ar, this message translates to:
  /// **'🎥 الفيديو التعليمي'**
  String get lessonWatchVideo;

  /// No description provided for @lessonFlashcards.
  ///
  /// In ar, this message translates to:
  /// **'📇 فلاش كاردز ({count} بطاقة)'**
  String lessonFlashcards(Object count);

  /// No description provided for @lessonQuiz.
  ///
  /// In ar, this message translates to:
  /// **'❓ اختبر نفسك ({count} سؤال)'**
  String lessonQuiz(Object count);

  /// No description provided for @lessonInfographic.
  ///
  /// In ar, this message translates to:
  /// **'📊 إنفوجرافيك الدرس'**
  String get lessonInfographic;

  /// No description provided for @lessonReport.
  ///
  /// In ar, this message translates to:
  /// **'📄 تقرير الدرس'**
  String get lessonReport;

  /// No description provided for @lessonDataTable.
  ///
  /// In ar, this message translates to:
  /// **'📋 جدول البيانات'**
  String get lessonDataTable;

  /// No description provided for @lessonPlayCyber.
  ///
  /// In ar, this message translates to:
  /// **'🎮 العب وتعلم (حارس البيانات)'**
  String get lessonPlayCyber;

  /// No description provided for @lessonPlayMedical.
  ///
  /// In ar, this message translates to:
  /// **'🎮 العب وتعلم'**
  String get lessonPlayMedical;

  /// No description provided for @lessonPlayIslamic.
  ///
  /// In ar, this message translates to:
  /// **'🎮 العب وتعلم (شجرة الأخلاق)'**
  String get lessonPlayIslamic;

  /// No description provided for @lessonPlayDev.
  ///
  /// In ar, this message translates to:
  /// **'🎮 العب وتعلم (متاهة المشاعر)'**
  String get lessonPlayDev;

  /// No description provided for @lessonVideoTitle.
  ///
  /// In ar, this message translates to:
  /// **'🎥 شاهد الفيديو التعليمي'**
  String get lessonVideoTitle;

  /// No description provided for @lessonPodcastTitle.
  ///
  /// In ar, this message translates to:
  /// **'🎧 البودكاست'**
  String get lessonPodcastTitle;

  /// No description provided for @lessonVideoUnitTitle.
  ///
  /// In ar, this message translates to:
  /// **'🎥 فيديو الوحدة: {title}'**
  String lessonVideoUnitTitle(Object title);

  /// No description provided for @lessonInteractiveHint.
  ///
  /// In ar, this message translates to:
  /// **'استمع، شاهد، والعب — ثم اقرأ الملخص بالأسفل'**
  String get lessonInteractiveHint;

  /// No description provided for @journeyTitle.
  ///
  /// In ar, this message translates to:
  /// **'رحلة {name}'**
  String journeyTitle(Object name);

  /// No description provided for @journeyLoading.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الرحلة.'**
  String get journeyLoading;

  /// No description provided for @journeyStartFirst.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ بتسجيل أول محطة في رحلته'**
  String get journeyStartFirst;

  /// No description provided for @journeyCount.
  ///
  /// In ar, this message translates to:
  /// **'سجّلت {count} محطة — سجّل تعتزّ به 💛'**
  String journeyCount(Object count);

  /// No description provided for @journeyMilestoneLog.
  ///
  /// In ar, this message translates to:
  /// **'سجّل محطة من عندك'**
  String get journeyMilestoneLog;

  /// No description provided for @journeyDeleteMilestone.
  ///
  /// In ar, this message translates to:
  /// **'حذف المحطة'**
  String get journeyDeleteMilestone;

  /// No description provided for @journeyDeleteConfirm.
  ///
  /// In ar, this message translates to:
  /// **'هل تريد حذف «{title}» من رحلة {name}؟'**
  String journeyDeleteConfirm(Object name, Object title);

  /// No description provided for @journeyFaithMilestones.
  ///
  /// In ar, this message translates to:
  /// **'محطات إيمانية 🕌'**
  String get journeyFaithMilestones;

  /// No description provided for @journeyDevMilestones.
  ///
  /// In ar, this message translates to:
  /// **'محطات نمائية 📈 (حسب العمر)'**
  String get journeyDevMilestones;

  /// No description provided for @journeyEmpty.
  ///
  /// In ar, this message translates to:
  /// **'كل طفل رحلة فريدة. سجّل أول محطة من المحطات القادمة بالأسفل.'**
  String get journeyEmpty;

  /// No description provided for @journeyNewMilestone.
  ///
  /// In ar, this message translates to:
  /// **'محطة جديدة'**
  String get journeyNewMilestone;

  /// No description provided for @journeyMilestoneTitle.
  ///
  /// In ar, this message translates to:
  /// **'عنوان المحطة'**
  String get journeyMilestoneTitle;

  /// No description provided for @journeyMilestoneHint.
  ///
  /// In ar, this message translates to:
  /// **'مثال: قال أول كلمة طيبة'**
  String get journeyMilestoneHint;

  /// No description provided for @journeyMilestoneNote.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظة (اختياري)'**
  String get journeyMilestoneNote;

  /// No description provided for @journeyMilestoneNoteHint.
  ///
  /// In ar, this message translates to:
  /// **'دوّن لحظة تتذكرها…'**
  String get journeyMilestoneNoteHint;

  /// No description provided for @journeyMilestoneSave.
  ///
  /// In ar, this message translates to:
  /// **'سجّل المحطة'**
  String get journeyMilestoneSave;

  /// No description provided for @journeyChallengeTitle.
  ///
  /// In ar, this message translates to:
  /// **'تحدّي {name} الحالي'**
  String journeyChallengeTitle(Object name);

  /// No description provided for @journeyChallengeDone.
  ///
  /// In ar, this message translates to:
  /// **'تم الحل ✓'**
  String get journeyChallengeDone;

  /// No description provided for @journeyChallengeDesc.
  ///
  /// In ar, this message translates to:
  /// **'اختر تحدّياً تركّز عليه الآن — وسيوجّه «المربّي» نصيحته اليومية إليه.'**
  String get journeyChallengeDesc;

  /// No description provided for @journeyChallengeActive.
  ///
  /// In ar, this message translates to:
  /// **'يركّز «المربّي» على هذا التحدّي في نصيحته اليومية.'**
  String get journeyChallengeActive;

  /// No description provided for @journeySaveError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ — تأكد من الاتصال.'**
  String get journeySaveError;

  /// No description provided for @journeyQuranTitle.
  ///
  /// In ar, this message translates to:
  /// **'حفظ القرآن'**
  String get journeyQuranTitle;

  /// No description provided for @journeyQuranTrack.
  ///
  /// In ar, this message translates to:
  /// **'تابع ما يحفظه — ونحتفل بأول سورة'**
  String get journeyQuranTrack;

  /// No description provided for @journeyQuranCount.
  ///
  /// In ar, this message translates to:
  /// **'حفظ {count} سورة'**
  String journeyQuranCount(Object count);

  /// No description provided for @pathDetailTitle.
  ///
  /// In ar, this message translates to:
  /// **'تفاصيل المسار'**
  String get pathDetailTitle;

  /// No description provided for @pathDetailLessons.
  ///
  /// In ar, this message translates to:
  /// **'الدروس ({count})'**
  String pathDetailLessons(Object count);

  /// No description provided for @pathDetailEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد دروس في هذا المسار بعد'**
  String get pathDetailEmpty;

  /// No description provided for @pathDetailStart.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ المسار'**
  String get pathDetailStart;

  /// No description provided for @pathDetailShare.
  ///
  /// In ar, this message translates to:
  /// **'شارك إتمام المسار 🤍'**
  String get pathDetailShare;

  /// No description provided for @pathDetailVideoUnit.
  ///
  /// In ar, this message translates to:
  /// **'🎥 فيديو الوحدة: {title}'**
  String pathDetailVideoUnit(Object title);

  /// No description provided for @pathDetailVideoIntro.
  ///
  /// In ar, this message translates to:
  /// **'🎥 فيديو تعريفي'**
  String get pathDetailVideoIntro;

  /// No description provided for @pathDetailVideoIntroTitle.
  ///
  /// In ar, this message translates to:
  /// **'🎥 فيديو تعريفي لـ {title}'**
  String pathDetailVideoIntroTitle(Object title);

  /// No description provided for @pathDetailDays.
  ///
  /// In ar, this message translates to:
  /// **'⏱️ {count} يوم'**
  String pathDetailDays(Object count);

  /// No description provided for @pathDetailLessonsCount.
  ///
  /// In ar, this message translates to:
  /// **'📚 {count} دروس'**
  String pathDetailLessonsCount(Object count);

  /// No description provided for @pathDetailStreakStart.
  ///
  /// In ar, this message translates to:
  /// **'🔥 ابدأ سلسلتك اليوم'**
  String get pathDetailStreakStart;

  /// No description provided for @pathDetailStreakDays.
  ///
  /// In ar, this message translates to:
  /// **'🔥 {count} يوم متتالي'**
  String pathDetailStreakDays(Object count);

  /// No description provided for @pathDetailRefMain.
  ///
  /// In ar, this message translates to:
  /// **'مرجع رئيسي'**
  String get pathDetailRefMain;

  /// No description provided for @pathDetailRefHadith.
  ///
  /// In ar, this message translates to:
  /// **'حديث'**
  String get pathDetailRefHadith;

  /// No description provided for @pathDetailRefResearch.
  ///
  /// In ar, this message translates to:
  /// **'بحث علمي'**
  String get pathDetailRefResearch;

  /// No description provided for @pathDetailRefDevArticle.
  ///
  /// In ar, this message translates to:
  /// **'مقال تنموي'**
  String get pathDetailRefDevArticle;

  /// No description provided for @pathDetailTrailLesson.
  ///
  /// In ar, this message translates to:
  /// **'الدرس {order}: {title}. {status}'**
  String pathDetailTrailLesson(Object order, Object status, Object title);

  /// No description provided for @pathDetailMinutes.
  ///
  /// In ar, this message translates to:
  /// **'⏱️ {count} د'**
  String pathDetailMinutes(Object count);

  /// No description provided for @pathDetailFollowup.
  ///
  /// In ar, this message translates to:
  /// **'متابعة متخصصة'**
  String get pathDetailFollowup;

  /// No description provided for @quizTitleAppBar.
  ///
  /// In ar, this message translates to:
  /// **'🧠 اختبر معلوماتك'**
  String get quizTitleAppBar;

  /// No description provided for @quizErrorLoading.
  ///
  /// In ar, this message translates to:
  /// **'خطأ في تحميل الأسئلة'**
  String get quizErrorLoading;

  /// No description provided for @quizErrorConnection.
  ///
  /// In ar, this message translates to:
  /// **'تعذر الاتصال بالخادم'**
  String get quizErrorConnection;

  /// No description provided for @quizExcellent.
  ///
  /// In ar, this message translates to:
  /// **'ممتاز! أنت مربي واعٍ'**
  String get quizExcellent;

  /// No description provided for @quizGood.
  ///
  /// In ar, this message translates to:
  /// **'جيد! واصل التعلم'**
  String get quizGood;

  /// No description provided for @quizKeepLearning.
  ///
  /// In ar, this message translates to:
  /// **'لا بأس، كل يوم فرصة للتعلم'**
  String get quizKeepLearning;

  /// No description provided for @quizPoints.
  ///
  /// In ar, this message translates to:
  /// **'نقطة'**
  String get quizPoints;

  /// No description provided for @quizShareResult.
  ///
  /// In ar, this message translates to:
  /// **'شارك نتيجتك 🤍'**
  String get quizShareResult;

  /// No description provided for @quizPlayAgain.
  ///
  /// In ar, this message translates to:
  /// **'العب مرة أخرى'**
  String get quizPlayAgain;

  /// No description provided for @quizBack.
  ///
  /// In ar, this message translates to:
  /// **'العودة'**
  String get quizBack;

  /// No description provided for @quizNext.
  ///
  /// In ar, this message translates to:
  /// **'السؤال التالي'**
  String get quizNext;

  /// No description provided for @quizShowResults.
  ///
  /// In ar, this message translates to:
  /// **'عرض النتائج'**
  String get quizShowResults;

  /// No description provided for @quizExcellentShare.
  ///
  /// In ar, this message translates to:
  /// **'ممتاز! 🏆'**
  String get quizExcellentShare;

  /// No description provided for @quizGoodShare.
  ///
  /// In ar, this message translates to:
  /// **'جيد! 👏'**
  String get quizGoodShare;

  /// No description provided for @quizKeepShare.
  ///
  /// In ar, this message translates to:
  /// **'واصل التعلم 💪'**
  String get quizKeepShare;

  /// No description provided for @quizResultTitle.
  ///
  /// In ar, this message translates to:
  /// **'نتيجة الاختبار'**
  String get quizResultTitle;

  /// No description provided for @quizPraiseExcellent.
  ///
  /// In ar, this message translates to:
  /// **'ممتاز! — واصل التعلم يوميًا مع المربّي.'**
  String get quizPraiseExcellent;

  /// No description provided for @quizPraiseGood.
  ///
  /// In ar, this message translates to:
  /// **'جيد! — واصل التعلم يوميًا مع المربّي.'**
  String get quizPraiseGood;

  /// No description provided for @quizPraiseKeep.
  ///
  /// In ar, this message translates to:
  /// **'واصل التعلم — كل يوم فرصة مع المربّي.'**
  String get quizPraiseKeep;

  /// No description provided for @covenantTitle.
  ///
  /// In ar, this message translates to:
  /// **'عهد المكافآت الواقعية 📜'**
  String get covenantTitle;

  /// No description provided for @covenantTabRedeem.
  ///
  /// In ar, this message translates to:
  /// **'استبدال العملات 🪙'**
  String get covenantTabRedeem;

  /// No description provided for @covenantTabParent.
  ///
  /// In ar, this message translates to:
  /// **'بوابة الأهل 🔑'**
  String get covenantTabParent;

  /// No description provided for @covenantBalanceLabel.
  ///
  /// In ar, this message translates to:
  /// **'رصيد عملاتك الحالي'**
  String get covenantBalanceLabel;

  /// No description provided for @covenantBalanceHint.
  ///
  /// In ar, this message translates to:
  /// **'استبدل العملات بمكافآت واقعية متفق عليها مع أهلك.'**
  String get covenantBalanceHint;

  /// No description provided for @covenantEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد مكافآت متاحة حالياً. اطلب من والديك إضافتها!'**
  String get covenantEmpty;

  /// No description provided for @covenantCost.
  ///
  /// In ar, this message translates to:
  /// **'التكلفة: {count} عملة 🪙'**
  String covenantCost(Object count);

  /// No description provided for @covenantRedeem.
  ///
  /// In ar, this message translates to:
  /// **'استبدال'**
  String get covenantRedeem;

  /// No description provided for @covenantRemaining.
  ///
  /// In ar, this message translates to:
  /// **'يتبقى {count}'**
  String covenantRemaining(Object count);

  /// No description provided for @covenantInsufficient.
  ///
  /// In ar, this message translates to:
  /// **'عذراً، رصيدك من العملات غير كافٍ! 🪙'**
  String get covenantInsufficient;

  /// No description provided for @covenantSuccess.
  ///
  /// In ar, this message translates to:
  /// **'🎉 تم الاستبدال بنجاح!'**
  String get covenantSuccess;

  /// No description provided for @covenantSuccessMsg.
  ///
  /// In ar, this message translates to:
  /// **'لقد قمت بطلب: \"{title}\" مقابل {cost} عملة. أخبر والديك ليقدماها لك بالواقع!'**
  String covenantSuccessMsg(Object cost, Object title);

  /// No description provided for @covenantDelivered.
  ///
  /// In ar, this message translates to:
  /// **'تم تسجيل تقديم المكافأة بنجاح! ✅'**
  String get covenantDelivered;

  /// No description provided for @covenantParentWelcome.
  ///
  /// In ar, this message translates to:
  /// **'بوابة الأهل: أضف مكافآت حقيقية يلتزم بها الأهل بالواقع (مثل رحلات أو هدايا)، وتابع طلبات طفلك لتسليمها.'**
  String get covenantParentWelcome;

  /// No description provided for @covenantAddNew.
  ///
  /// In ar, this message translates to:
  /// **'إضافة مكافأة جديدة ➕'**
  String get covenantAddNew;

  /// No description provided for @covenantPending.
  ///
  /// In ar, this message translates to:
  /// **'طلبات استبدال بانتظار تسليمها بالواقع ⏳'**
  String get covenantPending;

  /// No description provided for @covenantPendingEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد طلبات معلقة حالياً.'**
  String get covenantPendingEmpty;

  /// No description provided for @covenantPendingRedeemed.
  ///
  /// In ar, this message translates to:
  /// **'استبدلها طفلك مقابل {cost} عملة 🪙'**
  String covenantPendingRedeemed(Object cost);

  /// No description provided for @covenantDeliver.
  ///
  /// In ar, this message translates to:
  /// **'تم تقديمها ✅'**
  String get covenantDeliver;

  /// No description provided for @covenantManage.
  ///
  /// In ar, this message translates to:
  /// **'قائمة المكافآت المتاحة وإدارتها ⚙️'**
  String get covenantManage;

  /// No description provided for @covenantManageEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد مكافآت مضافة.'**
  String get covenantManageEmpty;

  /// No description provided for @covenantHistory.
  ///
  /// In ar, this message translates to:
  /// **'المكافآت التي تم تسليمها سابقاً ✅'**
  String get covenantHistory;

  /// No description provided for @covenantHistoryEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد مكافآت مسلّمة سابقاً.'**
  String get covenantHistoryEmpty;

  /// No description provided for @covenantHistoryRedeemed.
  ///
  /// In ar, this message translates to:
  /// **'استُبدلت بـ {cost} عملة'**
  String covenantHistoryRedeemed(Object cost);

  /// No description provided for @covenantAddTitle.
  ///
  /// In ar, this message translates to:
  /// **'إضافة مكافأة واقعية جديدة'**
  String get covenantAddTitle;

  /// No description provided for @covenantAddNameLabel.
  ///
  /// In ar, this message translates to:
  /// **'اسم المكافأة بالواقع (مثال: نزهة عائلية 🍦)'**
  String get covenantAddNameLabel;

  /// No description provided for @covenantAddCostLabel.
  ///
  /// In ar, this message translates to:
  /// **'تكلفة العملات 🪙'**
  String get covenantAddCostLabel;

  /// No description provided for @inviteTitle.
  ///
  /// In ar, this message translates to:
  /// **'ادعُ صديقًا 🤍'**
  String get inviteTitle;

  /// No description provided for @inviteDesc.
  ///
  /// In ar, this message translates to:
  /// **'دلالتك صديقًا على «المربّي» صدقة جارية — كل ما ينفع به طفله في ميزان حسناتك بإذن الله 🌿'**
  String get inviteDesc;

  /// No description provided for @inviteSharePreparing.
  ///
  /// In ar, this message translates to:
  /// **'جاري التحضير…'**
  String get inviteSharePreparing;

  /// No description provided for @inviteShareBtn.
  ///
  /// In ar, this message translates to:
  /// **'شارك الدعوة'**
  String get inviteShareBtn;

  /// No description provided for @inviteHaveCode.
  ///
  /// In ar, this message translates to:
  /// **'عندك كود من صديق؟'**
  String get inviteHaveCode;

  /// No description provided for @inviteActivate.
  ///
  /// In ar, this message translates to:
  /// **'تفعيل'**
  String get inviteActivate;

  /// No description provided for @inviteCodeCopied.
  ///
  /// In ar, this message translates to:
  /// **'تم نسخ الكود'**
  String get inviteCodeCopied;

  /// No description provided for @inviteYourCode.
  ///
  /// In ar, this message translates to:
  /// **'كود الإحالة الخاص بك'**
  String get inviteYourCode;

  /// No description provided for @inviteCodeUsed.
  ///
  /// In ar, this message translates to:
  /// **'دعوت {count} — جزاك الله خيرًا 🤍'**
  String inviteCodeUsed(Object count);

  /// No description provided for @inviteSuccess.
  ///
  /// In ar, this message translates to:
  /// **'تمّت إضافة الكود — جزى الله صديقك خيرًا 🤍 (+مكافأة)'**
  String get inviteSuccess;

  /// No description provided for @inviteAlreadyClaimed.
  ///
  /// In ar, this message translates to:
  /// **'سبق استخدام كود إحالة على هذا الجهاز.'**
  String get inviteAlreadyClaimed;

  /// No description provided for @inviteInvalidCode.
  ///
  /// In ar, this message translates to:
  /// **'كود غير صالح، تأكّد منه.'**
  String get inviteInvalidCode;

  /// No description provided for @inviteError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الاتصال، حاول لاحقًا.'**
  String get inviteError;

  /// No description provided for @childrenTitle.
  ///
  /// In ar, this message translates to:
  /// **'إدارة الأطفال'**
  String get childrenTitle;

  /// No description provided for @childrenEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد أطفال على هذا الجهاز. ابدأ بإضافة أول طفل.'**
  String get childrenEmpty;

  /// No description provided for @childrenAddNew.
  ///
  /// In ar, this message translates to:
  /// **'إضافة طفل جديد'**
  String get childrenAddNew;

  /// No description provided for @childrenMaxReached.
  ///
  /// In ar, this message translates to:
  /// **'وصلت للحد الأقصى ({count} أطفال). احذف طفلاً لإضافة طفل جديد.'**
  String childrenMaxReached(Object count);

  /// No description provided for @childrenCount.
  ///
  /// In ar, this message translates to:
  /// **'لديك {count} من أصل {max} أطفال'**
  String childrenCount(Object count, Object max);

  /// No description provided for @childrenSwitchTo.
  ///
  /// In ar, this message translates to:
  /// **'تم التبديل إلى {name}.'**
  String childrenSwitchTo(Object name);

  /// No description provided for @childrenSwitchError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر التبديل: {error}'**
  String childrenSwitchError(Object error);

  /// No description provided for @childrenActive.
  ///
  /// In ar, this message translates to:
  /// **'نشط'**
  String get childrenActive;

  /// No description provided for @childrenJourney.
  ///
  /// In ar, this message translates to:
  /// **'رحلة الطفل'**
  String get childrenJourney;

  /// No description provided for @childrenDelete.
  ///
  /// In ar, this message translates to:
  /// **'حذف الطفل'**
  String get childrenDelete;

  /// No description provided for @childrenDeleteConfirm.
  ///
  /// In ar, this message translates to:
  /// **'هل أنت متأكد من حذف «{name}»؟ سيُحذف ملفه نهائيًا.'**
  String childrenDeleteConfirm(Object name);

  /// No description provided for @childrenDeleted.
  ///
  /// In ar, this message translates to:
  /// **'تم حذف {name}.'**
  String childrenDeleted(Object name);

  /// No description provided for @childrenDeleteError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحذف: {error}'**
  String childrenDeleteError(Object error);

  /// No description provided for @childrenErrorLoading.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل قائمة الأطفال.'**
  String get childrenErrorLoading;

  /// No description provided for @childrenAgePrenatal.
  ///
  /// In ar, this message translates to:
  /// **'فترة الحمل وحتى عام'**
  String get childrenAgePrenatal;

  /// No description provided for @parentingInsightsTitle.
  ///
  /// In ar, this message translates to:
  /// **'تحليلات وتوصيات المربّي 🧠'**
  String get parentingInsightsTitle;

  /// No description provided for @parentingInsightsLoading.
  ///
  /// In ar, this message translates to:
  /// **'جاري تحليل نشاط طفلك وتوليد التوصيات...'**
  String get parentingInsightsLoading;

  /// No description provided for @parentingInsightsNoChild.
  ///
  /// In ar, this message translates to:
  /// **'يرجى اختيار طفل أولاً.'**
  String get parentingInsightsNoChild;

  /// No description provided for @parentingInsightsError.
  ///
  /// In ar, this message translates to:
  /// **'فشل تحميل البيانات. يرجى التحقق من اتصال الإنترنت.'**
  String get parentingInsightsError;

  /// No description provided for @parentingInsightsWelcome.
  ///
  /// In ar, this message translates to:
  /// **'أهلاً بك في التحليلات التربوية! نقوم بتحليل الروتين الأسبوعي ورسائل المحادثات لتقديم إرشادات مخصصة لرحلة تربية {name}.'**
  String parentingInsightsWelcome(Object name);

  /// No description provided for @parentingInsightsWeekly.
  ///
  /// In ar, this message translates to:
  /// **'النشاط الأسبوعي الأخير 📊'**
  String get parentingInsightsWeekly;

  /// No description provided for @parentingInsightsSleep.
  ///
  /// In ar, this message translates to:
  /// **'نوم'**
  String get parentingInsightsSleep;

  /// No description provided for @parentingInsightsFeeds.
  ///
  /// In ar, this message translates to:
  /// **'رضاعة وتغذية'**
  String get parentingInsightsFeeds;

  /// No description provided for @parentingInsightsDiapers.
  ///
  /// In ar, this message translates to:
  /// **'تغيير حفاظ'**
  String get parentingInsightsDiapers;

  /// No description provided for @parentingInsightsRecommendations.
  ///
  /// In ar, this message translates to:
  /// **'توصيات المربّي الذكي ✨'**
  String get parentingInsightsRecommendations;

  /// No description provided for @parentingInsightsNoData.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد توصيات كافية حالياً. استمر في تسجيل الروتين والمحادثات مع المساعد للحصول على توصيات مخصصة.'**
  String get parentingInsightsNoData;

  /// No description provided for @habitChildModeTitle.
  ///
  /// In ar, this message translates to:
  /// **'ميزان العادات'**
  String get habitChildModeTitle;

  /// No description provided for @habitChildModeExit.
  ///
  /// In ar, this message translates to:
  /// **'خروج'**
  String get habitChildModeExit;

  /// No description provided for @habitChildModeExitTitle.
  ///
  /// In ar, this message translates to:
  /// **'خروج من وضع الطفل'**
  String get habitChildModeExitTitle;

  /// No description provided for @habitChildModeExitConfirm.
  ///
  /// In ar, this message translates to:
  /// **'هل تريد الخروج من وضع الطفل والعودة لحساب المربي؟'**
  String get habitChildModeExitConfirm;

  /// No description provided for @habitChildModeLogged.
  ///
  /// In ar, this message translates to:
  /// **'تم التسجيل'**
  String get habitChildModeLogged;

  /// No description provided for @habitChildModeDone.
  ///
  /// In ar, this message translates to:
  /// **'تم'**
  String get habitChildModeDone;

  /// No description provided for @habitChildModePartial.
  ///
  /// In ar, this message translates to:
  /// **'جزئي'**
  String get habitChildModePartial;

  /// No description provided for @habitChildModeMissed.
  ///
  /// In ar, this message translates to:
  /// **'لم يتم'**
  String get habitChildModeMissed;

  /// No description provided for @habitChildModeConfirmTitle.
  ///
  /// In ar, this message translates to:
  /// **'تأكيد التسجيل'**
  String get habitChildModeConfirmTitle;

  /// No description provided for @habitChildModeConfirmMsg.
  ///
  /// In ar, this message translates to:
  /// **'هل أنت متأكد من تسجيل \"{name}\" كـ \"{label}\"؟ لا يمكن التعديل إلا من حساب المربي.'**
  String habitChildModeConfirmMsg(Object label, Object name);

  /// No description provided for @habitChildModeFailed.
  ///
  /// In ar, this message translates to:
  /// **'لم يتم التسجيل. حاول مرة أخرى.'**
  String get habitChildModeFailed;

  /// No description provided for @habitChildModeExpired.
  ///
  /// In ar, this message translates to:
  /// **'انتهى وقت الجلسة. يُرجى العودة للمربي.'**
  String get habitChildModeExpired;

  /// No description provided for @storyTitle.
  ///
  /// In ar, this message translates to:
  /// **'قصة مخصصة 📖'**
  String get storyTitle;

  /// No description provided for @storyThemeIntro.
  ///
  /// In ar, this message translates to:
  /// **'اختر قيمة تربوية، وسنؤلّف قصة قصيرة بطلها طفلك 🌟'**
  String get storyThemeIntro;

  /// No description provided for @storyGenerating.
  ///
  /// In ar, this message translates to:
  /// **'جارٍ تأليف القصة…'**
  String get storyGenerating;

  /// No description provided for @storyCost.
  ///
  /// In ar, this message translates to:
  /// **'توليد قصة ({count} 🪙)'**
  String storyCost(Object count);

  /// No description provided for @storyLoading.
  ///
  /// In ar, this message translates to:
  /// **'قد يستغرق هذا لحظات…'**
  String get storyLoading;

  /// No description provided for @storyAnother.
  ///
  /// In ar, this message translates to:
  /// **'قصة أخرى'**
  String get storyAnother;

  /// No description provided for @storyInsufficient.
  ///
  /// In ar, this message translates to:
  /// **'عذراً، رصيدك لا يكفي 🪙'**
  String get storyInsufficient;

  /// No description provided for @storyInsufficientMsg.
  ///
  /// In ar, this message translates to:
  /// **'تحتاج إلى {count} عملة لتأليف قصة مخصصة لطفلك. شارك التطبيق مع أصدقائك واحصل على {reward} عملة مجاناً عن كل صديق ينضم إلينا! 🌿'**
  String storyInsufficientMsg(Object count, Object reward);

  /// No description provided for @storyInviteBtn.
  ///
  /// In ar, this message translates to:
  /// **'ادعُ صديقاً (+{reward} 🪙)'**
  String storyInviteBtn(Object reward);

  /// No description provided for @storyError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر توليد القصة: {error}'**
  String storyError(Object error);

  /// No description provided for @pathsTitle.
  ///
  /// In ar, this message translates to:
  /// **'مساراتي 🛤️'**
  String get pathsTitle;

  /// No description provided for @pathsFilterAll.
  ///
  /// In ar, this message translates to:
  /// **'الكل'**
  String get pathsFilterAll;

  /// No description provided for @pathsEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد مسارات بعد'**
  String get pathsEmpty;

  /// No description provided for @pathsEmptyDesc.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد مسارات لهذه المرحلة العمرية حالياً.'**
  String get pathsEmptyDesc;

  /// No description provided for @pathsError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل المسارات'**
  String get pathsError;

  /// No description provided for @coinsTitle.
  ///
  /// In ar, this message translates to:
  /// **'عملاتي 🪙'**
  String get coinsTitle;

  /// No description provided for @coinsUnit.
  ///
  /// In ar, this message translates to:
  /// **'عملة'**
  String get coinsUnit;

  /// No description provided for @coinsStreak.
  ///
  /// In ar, this message translates to:
  /// **'🔥 سلسلة دخول {count} يوم'**
  String coinsStreak(Object count);

  /// No description provided for @coinsDailyClaim.
  ///
  /// In ar, this message translates to:
  /// **'احصل على مكافأة اليوم 🎁'**
  String get coinsDailyClaim;

  /// No description provided for @coinsRewardSnack.
  ///
  /// In ar, this message translates to:
  /// **'+{reward} عملة! 🪙'**
  String coinsRewardSnack(Object reward);

  /// No description provided for @coinsDailyDone.
  ///
  /// In ar, this message translates to:
  /// **'تم استلام مكافأة اليوم — عُد غداً!'**
  String get coinsDailyDone;

  /// No description provided for @coinsEarnHow.
  ///
  /// In ar, this message translates to:
  /// **'كيف تكسب العملات؟'**
  String get coinsEarnHow;

  /// No description provided for @coinsEarnDaily.
  ///
  /// In ar, this message translates to:
  /// **'تسجيل الدخول اليومي'**
  String get coinsEarnDaily;

  /// No description provided for @coinsEarnDailyDesc.
  ///
  /// In ar, this message translates to:
  /// **'+{count} عملة كل يوم، وتزيد مع السلسلة'**
  String coinsEarnDailyDesc(Object count);

  /// No description provided for @coinsEarnBadge.
  ///
  /// In ar, this message translates to:
  /// **'فتح إنجاز جديد'**
  String get coinsEarnBadge;

  /// No description provided for @coinsEarnBadgeDesc.
  ///
  /// In ar, this message translates to:
  /// **'+{count} عملة لكل شارة'**
  String coinsEarnBadgeDesc(Object count);

  /// No description provided for @coinsEarnInvite.
  ///
  /// In ar, this message translates to:
  /// **'دعوة صديق للانضمام'**
  String get coinsEarnInvite;

  /// No description provided for @coinsEarnInviteDesc.
  ///
  /// In ar, this message translates to:
  /// **'+{count} عملة لكل صديق يحمل التطبيق'**
  String coinsEarnInviteDesc(Object count);

  /// No description provided for @coinsRedeemTitle.
  ///
  /// In ar, this message translates to:
  /// **'استبدل عملاتك 🎁'**
  String get coinsRedeemTitle;

  /// No description provided for @coinsRedeemStory.
  ///
  /// In ar, this message translates to:
  /// **'قصة مخصصة لطفلك'**
  String get coinsRedeemStory;

  /// No description provided for @coinsRedeemStoryDesc.
  ///
  /// In ar, this message translates to:
  /// **'قصة قصيرة بطلها طفلك تعلّم قيمة تختارها'**
  String get coinsRedeemStoryDesc;

  /// No description provided for @coinsRedeemCovenant.
  ///
  /// In ar, this message translates to:
  /// **'عهد المكافآت الواقعية'**
  String get coinsRedeemCovenant;

  /// No description provided for @coinsRedeemCovenantDesc.
  ///
  /// In ar, this message translates to:
  /// **'استبدل العملات بمكافآت حقيقية متفق عليها مع أهلك'**
  String get coinsRedeemCovenantDesc;

  /// No description provided for @coinsRedeemBadges.
  ///
  /// In ar, this message translates to:
  /// **'شارات حصرية'**
  String get coinsRedeemBadges;

  /// No description provided for @coinsRedeemBadgesDesc.
  ///
  /// In ar, this message translates to:
  /// **'افتح شارات مميزة بعملاتك'**
  String get coinsRedeemBadgesDesc;

  /// No description provided for @favoritesTitle.
  ///
  /// In ar, this message translates to:
  /// **'المفضلة'**
  String get favoritesTitle;

  /// No description provided for @favoritesClearAll.
  ///
  /// In ar, this message translates to:
  /// **'مسح جميع المفضلة؟'**
  String get favoritesClearAll;

  /// No description provided for @favoritesClearAllMsg.
  ///
  /// In ar, this message translates to:
  /// **'سيتم إزالة كل الدروس والنصائح المحفوظة. لا يمكن التراجع.'**
  String get favoritesClearAllMsg;

  /// No description provided for @favoritesCleared.
  ///
  /// In ar, this message translates to:
  /// **'تم مسح جميع المفضلة'**
  String get favoritesCleared;

  /// No description provided for @favoritesSavedLessons.
  ///
  /// In ar, this message translates to:
  /// **'الدروس المحفوظة'**
  String get favoritesSavedLessons;

  /// No description provided for @favoritesSavedTips.
  ///
  /// In ar, this message translates to:
  /// **'النصائح المحفوظة'**
  String get favoritesSavedTips;

  /// No description provided for @favoritesEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد عناصر في المفضلة بعد'**
  String get favoritesEmpty;

  /// No description provided for @favoritesEmptyHint.
  ///
  /// In ar, this message translates to:
  /// **'اضغط أيقونة القلب ♡ على أي درس أو نصيحة\nلإضافتها هنا والوصول لها بسرعة.'**
  String get favoritesEmptyHint;

  /// No description provided for @favoritesErrorLoad.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل هذا العنصر المحفوظ'**
  String get favoritesErrorLoad;

  /// No description provided for @favoritesTipSaved.
  ///
  /// In ar, this message translates to:
  /// **'نصيحة يومية محفوظة'**
  String get favoritesTipSaved;

  /// No description provided for @editChildTitle.
  ///
  /// In ar, this message translates to:
  /// **'تعديل ملف الطفل'**
  String get editChildTitle;

  /// No description provided for @editChildSaving.
  ///
  /// In ar, this message translates to:
  /// **'جارٍ الحفظ…'**
  String get editChildSaving;

  /// No description provided for @editChildSaveBtn.
  ///
  /// In ar, this message translates to:
  /// **'حفظ التغييرات'**
  String get editChildSaveBtn;

  /// No description provided for @editChildSaved.
  ///
  /// In ar, this message translates to:
  /// **'تم حفظ التغييرات.'**
  String get editChildSaved;

  /// No description provided for @editChildSaveError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الحفظ: {error}'**
  String editChildSaveError(Object error);

  /// No description provided for @editChildName.
  ///
  /// In ar, this message translates to:
  /// **'اسم الطفل'**
  String get editChildName;

  /// No description provided for @editChildAge.
  ///
  /// In ar, this message translates to:
  /// **'المرحلة العمرية'**
  String get editChildAge;

  /// No description provided for @editChildAvatar.
  ///
  /// In ar, this message translates to:
  /// **'صورة الطفل'**
  String get editChildAvatar;

  /// No description provided for @editChildGender.
  ///
  /// In ar, this message translates to:
  /// **'الجنس'**
  String get editChildGender;

  /// No description provided for @addChildTitle.
  ///
  /// In ar, this message translates to:
  /// **'إضافة طفل'**
  String get addChildTitle;

  /// No description provided for @addChildAdding.
  ///
  /// In ar, this message translates to:
  /// **'جارٍ الإضافة…'**
  String get addChildAdding;

  /// No description provided for @addChildBtn.
  ///
  /// In ar, this message translates to:
  /// **'إضافة الطفل'**
  String get addChildBtn;

  /// No description provided for @addChildAdded.
  ///
  /// In ar, this message translates to:
  /// **'تمّت إضافة {name}.'**
  String addChildAdded(Object name);

  /// No description provided for @addChildError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر إضافة الطفل: {error}'**
  String addChildError(Object error);

  /// No description provided for @addChildNameHint.
  ///
  /// In ar, this message translates to:
  /// **'مثلاً: يوسف، مريم، زياد'**
  String get addChildNameHint;

  /// No description provided for @addChildAgeRequired.
  ///
  /// In ar, this message translates to:
  /// **'يرجى اختيار المرحلة العمرية.'**
  String get addChildAgeRequired;

  /// No description provided for @updateSplashTitle.
  ///
  /// In ar, this message translates to:
  /// **'تحديث رئيسي 🎉'**
  String get updateSplashTitle;

  /// No description provided for @updateSplashVersion.
  ///
  /// In ar, this message translates to:
  /// **'إصدار {version} — إيه الجديد؟'**
  String updateSplashVersion(Object version);

  /// No description provided for @updateSplashStart.
  ///
  /// In ar, this message translates to:
  /// **'ابدأ'**
  String get updateSplashStart;

  /// No description provided for @updateSplashOnce.
  ///
  /// In ar, this message translates to:
  /// **'مرّة واحدة فقط — لن تظهر هذه الشاشة مجدداً.'**
  String get updateSplashOnce;

  /// No description provided for @updateSplashFeature1.
  ///
  /// In ar, this message translates to:
  /// **'درسك الأول على بُعد ضغطة'**
  String get updateSplashFeature1;

  /// No description provided for @updateSplashFeature1Desc.
  ///
  /// In ar, this message translates to:
  /// **'بدل ما تدوّر في القائمة، الصفحة الرئيسية بتفتح لك درسًا مختارًا لعمر طفلك مباشرة.'**
  String get updateSplashFeature1Desc;

  /// No description provided for @updateSplashFeature2.
  ///
  /// In ar, this message translates to:
  /// **'الإشعارات بقت توصّلك للمكان الصح'**
  String get updateSplashFeature2;

  /// No description provided for @updateSplashFeature2Desc.
  ///
  /// In ar, this message translates to:
  /// **'ضغطة على التذكير بتفتح المسار اللي وقفت عنده فعلًا، مش الصفحة الرئيسية.'**
  String get updateSplashFeature2Desc;

  /// No description provided for @updateSplashFeature3.
  ///
  /// In ar, this message translates to:
  /// **'الدروس من التذكيرات بقت تتقفل'**
  String get updateSplashFeature3;

  /// No description provided for @updateSplashFeature3Desc.
  ///
  /// In ar, this message translates to:
  /// **'أي درس تفتحه من إشعار أو من المفضّلة بقى فيه زر «أتممت هذا الدرس» زي أي درس تاني.'**
  String get updateSplashFeature3Desc;

  /// No description provided for @updateSplashFeature4.
  ///
  /// In ar, this message translates to:
  /// **'هدوء تحت الغطاء'**
  String get updateSplashFeature4;

  /// No description provided for @updateSplashFeature4Desc.
  ///
  /// In ar, this message translates to:
  /// **'نظّفنا مصدر إزعاج في الخلفية كان بيستهلك من ثبات التطبيق دون داعٍ.'**
  String get updateSplashFeature4Desc;

  /// No description provided for @quranMemTitle.
  ///
  /// In ar, this message translates to:
  /// **'حفظ القرآن — {name}'**
  String quranMemTitle(Object name);

  /// No description provided for @quranMemCount.
  ///
  /// In ar, this message translates to:
  /// **'حفظ {count} من 114 سورة'**
  String quranMemCount(Object count);

  /// No description provided for @quranMemHint.
  ///
  /// In ar, this message translates to:
  /// **'علّم السور التي أتمّها — نحتفل بكل خطوة'**
  String get quranMemHint;

  /// No description provided for @quranMemFirstSurah.
  ///
  /// In ar, this message translates to:
  /// **'حفظ أول سورة — سورة {surah}'**
  String quranMemFirstSurah(Object surah);

  /// No description provided for @feedbackTitle.
  ///
  /// In ar, this message translates to:
  /// **'شاركنا رأيك'**
  String get feedbackTitle;

  /// No description provided for @feedbackRepliesTitle.
  ///
  /// In ar, this message translates to:
  /// **'ردودنا عليك 💬'**
  String get feedbackRepliesTitle;

  /// No description provided for @feedbackReplyFrom.
  ///
  /// In ar, this message translates to:
  /// **'فريق المربّي'**
  String get feedbackReplyFrom;

  /// No description provided for @feedbackDesc.
  ///
  /// In ar, this message translates to:
  /// **'رأيك يهمنا ويصل مباشرةً لفريق المربي الذكي. اكتب ملاحظتك أو سجّلها صوتياً.'**
  String get feedbackDesc;

  /// No description provided for @feedbackMessageLabel.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظتك'**
  String get feedbackMessageLabel;

  /// No description provided for @feedbackMessageHint.
  ///
  /// In ar, this message translates to:
  /// **'اكتب اقتراحك أو المشكلة التي واجهتك…'**
  String get feedbackMessageHint;

  /// No description provided for @feedbackRecording.
  ///
  /// In ar, this message translates to:
  /// **'جارٍ التسجيل… اضغط للإيقاف'**
  String get feedbackRecording;

  /// No description provided for @feedbackRecorded.
  ///
  /// In ar, this message translates to:
  /// **'تم تسجيل ملاحظة صوتية ✓'**
  String get feedbackRecorded;

  /// No description provided for @feedbackRecordOptional.
  ///
  /// In ar, this message translates to:
  /// **'سجّل ملاحظة صوتية (اختياري)'**
  String get feedbackRecordOptional;

  /// No description provided for @feedbackMicPermission.
  ///
  /// In ar, this message translates to:
  /// **'يلزم إذن الميكروفون لتسجيل ملاحظة صوتية.'**
  String get feedbackMicPermission;

  /// No description provided for @feedbackRecordError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر التسجيل الصوتي على هذا الجهاز — يمكنك الكتابة بدلاً منه.'**
  String get feedbackRecordError;

  /// No description provided for @feedbackEmpty.
  ///
  /// In ar, this message translates to:
  /// **'اكتب ملاحظتك أو سجّل رسالة صوتية أولاً.'**
  String get feedbackEmpty;

  /// No description provided for @feedbackAudioTooBig.
  ///
  /// In ar, this message translates to:
  /// **'الملف الصوتي كبير جدًا (أكبر من 2 ميجا). جرّب تسجيل أقصر.'**
  String get feedbackAudioTooBig;

  /// No description provided for @feedbackContactLabel.
  ///
  /// In ar, this message translates to:
  /// **'وسيلة تواصل (اختياري)'**
  String get feedbackContactLabel;

  /// No description provided for @feedbackContactHint.
  ///
  /// In ar, this message translates to:
  /// **'بريد أو رقم للرد عليك'**
  String get feedbackContactHint;

  /// No description provided for @feedbackSending.
  ///
  /// In ar, this message translates to:
  /// **'جارٍ الإرسال…'**
  String get feedbackSending;

  /// No description provided for @feedbackSent.
  ///
  /// In ar, this message translates to:
  /// **'وصلت ملاحظتك، شكراً لك! 🌿 (ID: {id})'**
  String feedbackSent(Object id);

  /// No description provided for @feedbackSendError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الإرسال: {error}'**
  String feedbackSendError(Object error);

  /// No description provided for @quizTurnsCount.
  ///
  /// In ar, this message translates to:
  /// **'{count} / {total}'**
  String quizTurnsCount(Object count, Object total);

  /// No description provided for @cardCount.
  ///
  /// In ar, this message translates to:
  /// **'البطاقة {current} من {total}'**
  String cardCount(Object current, Object total);

  /// No description provided for @tapToContinue.
  ///
  /// In ar, this message translates to:
  /// **'اضغط للقلب · اسحب للتالي'**
  String get tapToContinue;

  /// No description provided for @previousCard.
  ///
  /// In ar, this message translates to:
  /// **'السابقة'**
  String get previousCard;

  /// No description provided for @nextCard.
  ///
  /// In ar, this message translates to:
  /// **'التالية'**
  String get nextCard;

  /// No description provided for @finishedCards.
  ///
  /// In ar, this message translates to:
  /// **'أنهيت البطاقات! 🎉'**
  String get finishedCards;

  /// No description provided for @habitCategoryWorship.
  ///
  /// In ar, this message translates to:
  /// **'العبادات'**
  String get habitCategoryWorship;

  /// No description provided for @habitCategorySelfBuilding.
  ///
  /// In ar, this message translates to:
  /// **'بناء الذات'**
  String get habitCategorySelfBuilding;

  /// No description provided for @habitCategoryStudy.
  ///
  /// In ar, this message translates to:
  /// **'المذاكرة'**
  String get habitCategoryStudy;

  /// No description provided for @habitPrayerFajr.
  ///
  /// In ar, this message translates to:
  /// **'صلاة الفجر'**
  String get habitPrayerFajr;

  /// No description provided for @habitPrayerDhuhr.
  ///
  /// In ar, this message translates to:
  /// **'صلاة الظهر'**
  String get habitPrayerDhuhr;

  /// No description provided for @habitPrayerAsr.
  ///
  /// In ar, this message translates to:
  /// **'صلاة العصر'**
  String get habitPrayerAsr;

  /// No description provided for @habitPrayerMaghrib.
  ///
  /// In ar, this message translates to:
  /// **'صلاة المغرب'**
  String get habitPrayerMaghrib;

  /// No description provided for @habitPrayerIsha.
  ///
  /// In ar, this message translates to:
  /// **'صلاة العشاء'**
  String get habitPrayerIsha;

  /// No description provided for @habitQuranWerd.
  ///
  /// In ar, this message translates to:
  /// **'ورد القرآن'**
  String get habitQuranWerd;

  /// No description provided for @habitQuranReading.
  ///
  /// In ar, this message translates to:
  /// **'قراءة القرآن'**
  String get habitQuranReading;

  /// No description provided for @habitHonoringParents.
  ///
  /// In ar, this message translates to:
  /// **'بر الوالدين'**
  String get habitHonoringParents;

  /// No description provided for @habitHonesty.
  ///
  /// In ar, this message translates to:
  /// **'الصدق'**
  String get habitHonesty;

  /// No description provided for @habitRespectElders.
  ///
  /// In ar, this message translates to:
  /// **'احترام الكبار'**
  String get habitRespectElders;

  /// No description provided for @habitTidyRoom.
  ///
  /// In ar, this message translates to:
  /// **'ترتيب الغرفة'**
  String get habitTidyRoom;

  /// No description provided for @habitEarlySleep.
  ///
  /// In ar, this message translates to:
  /// **'النوم المبكر'**
  String get habitEarlySleep;

  /// No description provided for @habitAngerControl.
  ///
  /// In ar, this message translates to:
  /// **'التحكم بالغضب'**
  String get habitAngerControl;

  /// No description provided for @habitHomework.
  ///
  /// In ar, this message translates to:
  /// **'أداء الواجب'**
  String get habitHomework;

  /// No description provided for @habitRevision.
  ///
  /// In ar, this message translates to:
  /// **'المراجعة'**
  String get habitRevision;

  /// No description provided for @habitReading.
  ///
  /// In ar, this message translates to:
  /// **'القراءة'**
  String get habitReading;

  /// No description provided for @routineEventSleep.
  ///
  /// In ar, this message translates to:
  /// **'نوم'**
  String get routineEventSleep;

  /// No description provided for @routineEventFeed.
  ///
  /// In ar, this message translates to:
  /// **'رضاعة'**
  String get routineEventFeed;

  /// No description provided for @routineEventDiaper.
  ///
  /// In ar, this message translates to:
  /// **'حفاظ'**
  String get routineEventDiaper;

  /// No description provided for @routineStatFeeds.
  ///
  /// In ar, this message translates to:
  /// **'رضاعات'**
  String get routineStatFeeds;

  /// No description provided for @routineStatDiapers.
  ///
  /// In ar, this message translates to:
  /// **'حفاظات'**
  String get routineStatDiapers;

  /// No description provided for @routineChildStage.
  ///
  /// In ar, this message translates to:
  /// **'الطفل {name} في مرحلة {stage}'**
  String routineChildStage(Object name, Object stage);

  /// No description provided for @errorGeneric.
  ///
  /// In ar, this message translates to:
  /// **'خطأ: {error}'**
  String errorGeneric(Object error);

  /// No description provided for @routineSummaryDays.
  ///
  /// In ar, this message translates to:
  /// **'ملخّص {days} أيام'**
  String routineSummaryDays(Object days);

  /// No description provided for @routineFieldType.
  ///
  /// In ar, this message translates to:
  /// **'نوع'**
  String get routineFieldType;

  /// No description provided for @routineFieldSide.
  ///
  /// In ar, this message translates to:
  /// **'جانب'**
  String get routineFieldSide;

  /// No description provided for @routineFieldDuration.
  ///
  /// In ar, this message translates to:
  /// **'مدة'**
  String get routineFieldDuration;

  /// No description provided for @routineAddEventTitle.
  ///
  /// In ar, this message translates to:
  /// **'إضافة حدث {type}'**
  String routineAddEventTitle(Object type);

  /// No description provided for @routineFeedBreast.
  ///
  /// In ar, this message translates to:
  /// **'ثدي'**
  String get routineFeedBreast;

  /// No description provided for @routineFeedBottle.
  ///
  /// In ar, this message translates to:
  /// **'رضّاعة'**
  String get routineFeedBottle;

  /// No description provided for @routineFeedSolid.
  ///
  /// In ar, this message translates to:
  /// **'طعام صلب'**
  String get routineFeedSolid;

  /// No description provided for @routineSideLeft.
  ///
  /// In ar, this message translates to:
  /// **'يسار'**
  String get routineSideLeft;

  /// No description provided for @routineSideRight.
  ///
  /// In ar, this message translates to:
  /// **'يمين'**
  String get routineSideRight;

  /// No description provided for @routineAmountApprox.
  ///
  /// In ar, this message translates to:
  /// **'الكمية تقريباً (ml)'**
  String get routineAmountApprox;

  /// No description provided for @routineDiaperWet.
  ///
  /// In ar, this message translates to:
  /// **'بلل'**
  String get routineDiaperWet;

  /// No description provided for @routineDiaperDirty.
  ///
  /// In ar, this message translates to:
  /// **'براز'**
  String get routineDiaperDirty;

  /// No description provided for @routinePickWakeTime.
  ///
  /// In ar, this message translates to:
  /// **'اختر وقت الاستيقاظ'**
  String get routinePickWakeTime;

  /// No description provided for @routineMedicalNoteBlocked.
  ///
  /// In ar, this message translates to:
  /// **'الملاحظة تحتوي على مصطلح طبي/دواء. رجاءً اكتب ملاحظة روتينية فقط.'**
  String get routineMedicalNoteBlocked;

  /// No description provided for @routineQrFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذر إنشاء رمز QR: {error}'**
  String routineQrFailed(Object error);

  /// No description provided for @routineShareTeenTitle.
  ///
  /// In ar, this message translates to:
  /// **'شارك الميزان مع المراهق'**
  String get routineShareTeenTitle;

  /// No description provided for @routineShareScanHint.
  ///
  /// In ar, this message translates to:
  /// **'امسح الرمز من هاتف الابن، أو انسخ الرابط وأرسله عبر واتساب.'**
  String get routineShareScanHint;

  /// No description provided for @childFallbackName.
  ///
  /// In ar, this message translates to:
  /// **'الطفل'**
  String get childFallbackName;

  /// No description provided for @childYourChild.
  ///
  /// In ar, this message translates to:
  /// **'طفلك'**
  String get childYourChild;

  /// No description provided for @childModePinRequired.
  ///
  /// In ar, this message translates to:
  /// **'يجب تحديد رمز PIN.'**
  String get childModePinRequired;

  /// No description provided for @childModePinIncorrect.
  ///
  /// In ar, this message translates to:
  /// **'الرمز غير صحيح.'**
  String get childModePinIncorrect;

  /// No description provided for @childModePinMismatch.
  ///
  /// In ar, this message translates to:
  /// **'الرقم غير متطابق. حاول مرة أخرى.'**
  String get childModePinMismatch;

  /// No description provided for @childModeSessionExpired.
  ///
  /// In ar, this message translates to:
  /// **'انتهى وقت الجلسة الآمنة. يُرجى إعادة الهاتف للمربي.'**
  String get childModeSessionExpired;

  /// No description provided for @childModeEnterFailed.
  ///
  /// In ar, this message translates to:
  /// **'فشل الدخول لوضع الطفل.'**
  String get childModeEnterFailed;

  /// No description provided for @habitCustomizeNameLabel.
  ///
  /// In ar, this message translates to:
  /// **'اسم العادة الجديدة'**
  String get habitCustomizeNameLabel;

  /// No description provided for @habitCustomizeNameHint.
  ///
  /// In ar, this message translates to:
  /// **'مثال: تمرين السباحة'**
  String get habitCustomizeNameHint;

  /// No description provided for @habitCustomizeNameLength.
  ///
  /// In ar, this message translates to:
  /// **'اسم العادة يجب أن يكون بين 2 و 60 حرفاً'**
  String get habitCustomizeNameLength;

  /// No description provided for @habitCustomizeAdded.
  ///
  /// In ar, this message translates to:
  /// **'تمت إضافة العادة'**
  String get habitCustomizeAdded;

  /// No description provided for @habitCustomizeAddFailed.
  ///
  /// In ar, this message translates to:
  /// **'فشل الإضافة: {error}'**
  String habitCustomizeAddFailed(Object error);

  /// No description provided for @habitCustomizeUpdateFailed.
  ///
  /// In ar, this message translates to:
  /// **'فشل التحديث: {error}'**
  String habitCustomizeUpdateFailed(Object error);

  /// No description provided for @insightHoursMinutes.
  ///
  /// In ar, this message translates to:
  /// **'{h} س {m} د'**
  String insightHoursMinutes(Object h, Object m);

  /// No description provided for @insightMinutes.
  ///
  /// In ar, this message translates to:
  /// **'{m} دقيقة'**
  String insightMinutes(Object m);

  /// No description provided for @insightTimesWithMl.
  ///
  /// In ar, this message translates to:
  /// **'{count} مرات\n({ml} مل)'**
  String insightTimesWithMl(Object count, Object ml);

  /// No description provided for @insightTimes.
  ///
  /// In ar, this message translates to:
  /// **'{count} مرات'**
  String insightTimes(Object count);

  /// No description provided for @insightBadgePositive.
  ///
  /// In ar, this message translates to:
  /// **'✅ إيجابي'**
  String get insightBadgePositive;

  /// No description provided for @insightBadgeWarning.
  ///
  /// In ar, this message translates to:
  /// **'⚠️ تنبيه'**
  String get insightBadgeWarning;

  /// No description provided for @insightBadgeTip.
  ///
  /// In ar, this message translates to:
  /// **'💡 نصيحة'**
  String get insightBadgeTip;

  /// No description provided for @ageGroupPrenatal.
  ///
  /// In ar, this message translates to:
  /// **'فترة الحمل وحتى عام'**
  String get ageGroupPrenatal;

  /// No description provided for @ageGroup2to3.
  ///
  /// In ar, this message translates to:
  /// **'2–3 سنوات'**
  String get ageGroup2to3;

  /// No description provided for @ageGroup4to6.
  ///
  /// In ar, this message translates to:
  /// **'4–6 سنوات'**
  String get ageGroup4to6;

  /// No description provided for @ageGroup7to9.
  ///
  /// In ar, this message translates to:
  /// **'7–9 سنوات'**
  String get ageGroup7to9;

  /// No description provided for @ageGroup10to12.
  ///
  /// In ar, this message translates to:
  /// **'10–12 سنة'**
  String get ageGroup10to12;

  /// No description provided for @ageGroup13to15.
  ///
  /// In ar, this message translates to:
  /// **'13–15 سنة'**
  String get ageGroup13to15;

  /// No description provided for @ageGroup16to18.
  ///
  /// In ar, this message translates to:
  /// **'16–18 سنة'**
  String get ageGroup16to18;

  /// No description provided for @unspecified.
  ///
  /// In ar, this message translates to:
  /// **'غير محدد'**
  String get unspecified;

  /// No description provided for @severityLight.
  ///
  /// In ar, this message translates to:
  /// **'خفيف'**
  String get severityLight;

  /// No description provided for @severityModerate.
  ///
  /// In ar, this message translates to:
  /// **'متوسط'**
  String get severityModerate;

  /// No description provided for @severitySevere.
  ///
  /// In ar, this message translates to:
  /// **'شديد'**
  String get severitySevere;

  /// No description provided for @severityEmergency.
  ///
  /// In ar, this message translates to:
  /// **'طارئ'**
  String get severityEmergency;

  /// No description provided for @domainMedical.
  ///
  /// In ar, this message translates to:
  /// **'العادات والمهارات الحياتية'**
  String get domainMedical;

  /// No description provided for @domainCyber.
  ///
  /// In ar, this message translates to:
  /// **'الأمان الرقمي'**
  String get domainCyber;

  /// No description provided for @domainIslamicParenting.
  ///
  /// In ar, this message translates to:
  /// **'التربية الإسلامية'**
  String get domainIslamicParenting;

  /// No description provided for @domainAqeedah.
  ///
  /// In ar, this message translates to:
  /// **'العقيدة'**
  String get domainAqeedah;

  /// No description provided for @domainDevelopment.
  ///
  /// In ar, this message translates to:
  /// **'تطور الطفل'**
  String get domainDevelopment;

  /// No description provided for @replyModeRetrieval.
  ///
  /// In ar, this message translates to:
  /// **'بحث فقط'**
  String get replyModeRetrieval;

  /// No description provided for @replyModeAi.
  ///
  /// In ar, this message translates to:
  /// **'ذكاء اصطناعي'**
  String get replyModeAi;

  /// No description provided for @replyModeBanned.
  ///
  /// In ar, this message translates to:
  /// **'خارج النطاق'**
  String get replyModeBanned;

  /// No description provided for @replyModeEmergency.
  ///
  /// In ar, this message translates to:
  /// **'حالة طارئة'**
  String get replyModeEmergency;

  /// No description provided for @escalationPediatrician.
  ///
  /// In ar, this message translates to:
  /// **'طبيب أطفال'**
  String get escalationPediatrician;

  /// No description provided for @escalationCyberSpecialist.
  ///
  /// In ar, this message translates to:
  /// **'متخصص بالأمان الرقمي'**
  String get escalationCyberSpecialist;

  /// No description provided for @escalationEmergencyServices.
  ///
  /// In ar, this message translates to:
  /// **'خدمات الطوارئ'**
  String get escalationEmergencyServices;

  /// No description provided for @apiTimeout.
  ///
  /// In ar, this message translates to:
  /// **'انتهت مهلة الاتصال بالخادم.'**
  String get apiTimeout;

  /// No description provided for @apiConnectionFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الاتصال بالخادم: {error}'**
  String apiConnectionFailed(Object error);

  /// No description provided for @apiNoSession.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد جلسة نشطة.'**
  String get apiNoSession;

  /// No description provided for @apiSessionNotFound.
  ///
  /// In ar, this message translates to:
  /// **'الجلسة غير موجودة على الخادم.'**
  String get apiSessionNotFound;

  /// No description provided for @apiSessionExpired.
  ///
  /// In ar, this message translates to:
  /// **'انتهت صلاحية الجلسة.'**
  String get apiSessionExpired;

  /// No description provided for @apiGoogleLinkFailed.
  ///
  /// In ar, this message translates to:
  /// **'فشل ربط حساب Google'**
  String get apiGoogleLinkFailed;

  /// No description provided for @apiChildSessionExpired.
  ///
  /// In ar, this message translates to:
  /// **'انتهى وقت جلسة الطفل الآمنة. يُرجى إعادة الهاتف للمربي.'**
  String get apiChildSessionExpired;

  /// No description provided for @apiIncompleteResponse.
  ///
  /// In ar, this message translates to:
  /// **'استجابة الخادم غير مكتملة.'**
  String get apiIncompleteResponse;

  /// No description provided for @apiServerError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ في الخادم.'**
  String get apiServerError;

  /// No description provided for @apiHttpError.
  ///
  /// In ar, this message translates to:
  /// **'خطأ HTTP {status}'**
  String apiHttpError(Object status);

  /// No description provided for @chatSessionStartFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر بدء جلسة: {error}'**
  String chatSessionStartFailed(Object error);

  /// No description provided for @chatNewChatFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر بدء محادثة جديدة: {error}'**
  String chatNewChatFailed(Object error);

  /// No description provided for @chatOfflineRetry.
  ///
  /// In ar, this message translates to:
  /// **'غير متصل بالإنترنت. تحقّق من الاتصال وأعد المحاولة.'**
  String get chatOfflineRetry;

  /// No description provided for @chatUnexpectedError.
  ///
  /// In ar, this message translates to:
  /// **'خطأ غير متوقع: {error}'**
  String chatUnexpectedError(Object error);

  /// No description provided for @chatConnectionInterrupted.
  ///
  /// In ar, this message translates to:
  /// **'انقطع الاتصال قبل اكتمال الرد.'**
  String get chatConnectionInterrupted;

  /// No description provided for @chatResponseStopped.
  ///
  /// In ar, this message translates to:
  /// **'⏹️ تم إيقاف الرد.'**
  String get chatResponseStopped;

  /// No description provided for @chatRatingSaveFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر حفظ التقييم: {error}'**
  String chatRatingSaveFailed(Object error);

  /// No description provided for @chatOpenFailed.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر فتح المحادثة: {error}'**
  String chatOpenFailed(Object error);

  /// No description provided for @chatFallbackTitle.
  ///
  /// In ar, this message translates to:
  /// **'محادثة'**
  String get chatFallbackTitle;

  /// No description provided for @safetyEmergencyText.
  ///
  /// In ar, this message translates to:
  /// **'حالة طارئة — يرجى التواصل مع الجهات المختصة فوراً.'**
  String get safetyEmergencyText;

  /// No description provided for @safetyEmergencyCta.
  ///
  /// In ar, this message translates to:
  /// **'اتصال بالطوارئ'**
  String get safetyEmergencyCta;

  /// No description provided for @safetyBannedText.
  ///
  /// In ar, this message translates to:
  /// **'هذا الموضوع خارج نطاق ما يمكنني مساعدتك فيه.'**
  String get safetyBannedText;

  /// No description provided for @safetyConsultPediatrician.
  ///
  /// In ar, this message translates to:
  /// **'استشر طبيب أطفال.'**
  String get safetyConsultPediatrician;

  /// No description provided for @safetyConsultCyberSpecialist.
  ///
  /// In ar, this message translates to:
  /// **'استشر متخصصاً في الأمان الرقمي.'**
  String get safetyConsultCyberSpecialist;

  /// No description provided for @safetyConsultHuman.
  ///
  /// In ar, this message translates to:
  /// **'من الأفضل مراجعة مختص بشري.'**
  String get safetyConsultHuman;

  /// No description provided for @safetyGeneralGuidance.
  ///
  /// In ar, this message translates to:
  /// **'هذا التوجيه عام — {hint}'**
  String safetyGeneralGuidance(Object hint);

  /// No description provided for @feedbackThanks.
  ///
  /// In ar, this message translates to:
  /// **'شكراً على تقييمك'**
  String get feedbackThanks;

  /// No description provided for @feedbackHelpful.
  ///
  /// In ar, this message translates to:
  /// **'إجابة مفيدة'**
  String get feedbackHelpful;

  /// No description provided for @feedbackNotHelpful.
  ///
  /// In ar, this message translates to:
  /// **'إجابة غير مفيدة'**
  String get feedbackNotHelpful;

  /// No description provided for @sharePreparing.
  ///
  /// In ar, this message translates to:
  /// **'جاري التحضير…'**
  String get sharePreparing;

  /// No description provided for @shareThisMoment.
  ///
  /// In ar, this message translates to:
  /// **'شارك هذه اللحظة 🤍'**
  String get shareThisMoment;

  /// No description provided for @communityProof.
  ///
  /// In ar, this message translates to:
  /// **'{count} أبٍ وأمٍّ يربّون بثقة مع «المربّي» — لست وحدك في الرحلة'**
  String communityProof(Object count);

  /// No description provided for @pathDomainIslamic.
  ///
  /// In ar, this message translates to:
  /// **'تربية إسلامية'**
  String get pathDomainIslamic;

  /// No description provided for @pathDomainAqeedah.
  ///
  /// In ar, this message translates to:
  /// **'العقيدة'**
  String get pathDomainAqeedah;

  /// No description provided for @pathDomainDevelopment.
  ///
  /// In ar, this message translates to:
  /// **'تنمية'**
  String get pathDomainDevelopment;

  /// No description provided for @pathDomainSkills.
  ///
  /// In ar, this message translates to:
  /// **'مهارات'**
  String get pathDomainSkills;

  /// No description provided for @pathDomainCyber.
  ///
  /// In ar, this message translates to:
  /// **'أمان رقمي'**
  String get pathDomainCyber;

  /// No description provided for @timeOfDayMorning.
  ///
  /// In ar, this message translates to:
  /// **'صباحاً'**
  String get timeOfDayMorning;

  /// No description provided for @timeOfDayEvening.
  ///
  /// In ar, this message translates to:
  /// **'مساءً'**
  String get timeOfDayEvening;

  /// No description provided for @timeOfDayBedtime.
  ///
  /// In ar, this message translates to:
  /// **'قبل النوم'**
  String get timeOfDayBedtime;

  /// No description provided for @timeOfDayAnytime.
  ///
  /// In ar, this message translates to:
  /// **'أي وقت'**
  String get timeOfDayAnytime;

  /// No description provided for @shareTipOfDayFor.
  ///
  /// In ar, this message translates to:
  /// **'نصيحة اليوم لـ {name}'**
  String shareTipOfDayFor(Object name);

  /// No description provided for @shareTagline.
  ///
  /// In ar, this message translates to:
  /// **'شريكك في رحلة التربية'**
  String get shareTagline;

  /// No description provided for @shareStoreHint.
  ///
  /// In ar, this message translates to:
  /// **'📲 مجانًا على Google Play — ابحث: «المربّي»'**
  String get shareStoreHint;

  /// No description provided for @eduGameChooseLevel.
  ///
  /// In ar, this message translates to:
  /// **'اختر المستوى'**
  String get eduGameChooseLevel;

  /// No description provided for @eduGameAttempts.
  ///
  /// In ar, this message translates to:
  /// **'المحاولات'**
  String get eduGameAttempts;

  /// No description provided for @eduGamePoints.
  ///
  /// In ar, this message translates to:
  /// **'النقاط'**
  String get eduGamePoints;

  /// No description provided for @eduGameStars.
  ///
  /// In ar, this message translates to:
  /// **'النجوم'**
  String get eduGameStars;

  /// No description provided for @eduGameBestScore.
  ///
  /// In ar, this message translates to:
  /// **'أفضل: {score}'**
  String eduGameBestScore(Object score);

  /// No description provided for @eduGamePaused.
  ///
  /// In ar, this message translates to:
  /// **'⏸️ توقفت'**
  String get eduGamePaused;

  /// No description provided for @eduGameResume.
  ///
  /// In ar, this message translates to:
  /// **'استئناف'**
  String get eduGameResume;

  /// No description provided for @eduGameRestartLevel.
  ///
  /// In ar, this message translates to:
  /// **'إعادة المستوى'**
  String get eduGameRestartLevel;

  /// No description provided for @eduGameQuit.
  ///
  /// In ar, this message translates to:
  /// **'خروج'**
  String get eduGameQuit;

  /// No description provided for @eduGameLevelComplete.
  ///
  /// In ar, this message translates to:
  /// **'مستوى مكتمل! 🎉'**
  String get eduGameLevelComplete;

  /// No description provided for @eduGameOver.
  ///
  /// In ar, this message translates to:
  /// **'انتهت اللعبة'**
  String get eduGameOver;

  /// No description provided for @eduGameCorrectAnswers.
  ///
  /// In ar, this message translates to:
  /// **'{correct} / {total} إجابات صحيحة'**
  String eduGameCorrectAnswers(Object correct, Object total);

  /// No description provided for @eduGameScore.
  ///
  /// In ar, this message translates to:
  /// **'النقاط: {score}'**
  String eduGameScore(Object score);

  /// No description provided for @eduGameTryAgain.
  ///
  /// In ar, this message translates to:
  /// **'حاول تاني! كل محاولة بتعلّمك أكتر.'**
  String get eduGameTryAgain;

  /// No description provided for @eduGameNextLevel.
  ///
  /// In ar, this message translates to:
  /// **'المستوى التالي ▶'**
  String get eduGameNextLevel;

  /// No description provided for @eduGameReplay.
  ///
  /// In ar, this message translates to:
  /// **'إعادة'**
  String get eduGameReplay;

  /// No description provided for @eduGameLevelTitle.
  ///
  /// In ar, this message translates to:
  /// **'{name} — مستوى {level}'**
  String eduGameLevelTitle(Object level, Object name);

  /// No description provided for @eduGameOptionLetters.
  ///
  /// In ar, this message translates to:
  /// **'أ,ب,ج,د'**
  String get eduGameOptionLetters;

  /// No description provided for @flashcardAnswer.
  ///
  /// In ar, this message translates to:
  /// **'الإجابة'**
  String get flashcardAnswer;

  /// No description provided for @journeyCardTitle.
  ///
  /// In ar, this message translates to:
  /// **'رحلة {name}'**
  String journeyCardTitle(Object name);

  /// No description provided for @journeyCardEmpty.
  ///
  /// In ar, this message translates to:
  /// **'سجّل محطات نموّه الإيمانية واحتفظ بها'**
  String get journeyCardEmpty;

  /// No description provided for @journeyCardCount.
  ///
  /// In ar, this message translates to:
  /// **'{count} محطة في رحلته — أضف المزيد'**
  String journeyCardCount(Object count);

  /// No description provided for @pathDetailStreakDay1.
  ///
  /// In ar, this message translates to:
  /// **'يوم متتالي'**
  String get pathDetailStreakDay1;

  /// No description provided for @pathDetailStreakDay2.
  ///
  /// In ar, this message translates to:
  /// **'يومان متتاليان'**
  String get pathDetailStreakDay2;

  /// No description provided for @pathDetailStreakDaysFew.
  ///
  /// In ar, this message translates to:
  /// **'أيام متتالية'**
  String get pathDetailStreakDaysFew;

  /// No description provided for @pathDetailStreakDaysMany.
  ///
  /// In ar, this message translates to:
  /// **'يوم متتالٍ'**
  String get pathDetailStreakDaysMany;

  /// No description provided for @pathsRefreshTooltip.
  ///
  /// In ar, this message translates to:
  /// **'تحديث'**
  String get pathsRefreshTooltip;

  /// No description provided for @pathsFilterSemantics.
  ///
  /// In ar, this message translates to:
  /// **'تصفية: {label}'**
  String pathsFilterSemantics(Object label);

  /// No description provided for @pathsPathSemantics.
  ///
  /// In ar, this message translates to:
  /// **'مسار: {title}. {description}'**
  String pathsPathSemantics(Object description, Object title);

  /// No description provided for @pathsFrameworkProphetic.
  ///
  /// In ar, this message translates to:
  /// **'المنهج النبوي 7-7-7'**
  String get pathsFrameworkProphetic;

  /// No description provided for @pathsFrameworkGhazali.
  ///
  /// In ar, this message translates to:
  /// **'تزكية الغزالي'**
  String get pathsFrameworkGhazali;

  /// No description provided for @pathsFrameworkAttachment.
  ///
  /// In ar, this message translates to:
  /// **'الرابطة والرحمة'**
  String get pathsFrameworkAttachment;

  /// No description provided for @pathsFrameworkZpd.
  ///
  /// In ar, this message translates to:
  /// **'منطقة النمو القريبة'**
  String get pathsFrameworkZpd;

  /// No description provided for @lessonNumberBadge.
  ///
  /// In ar, this message translates to:
  /// **'الدرس {order}'**
  String lessonNumberBadge(Object order);

  /// No description provided for @lessonMinutesBadge.
  ///
  /// In ar, this message translates to:
  /// **'⏱️ {count} دقائق'**
  String lessonMinutesBadge(Object count);

  /// No description provided for @lessonTempScreen.
  ///
  /// In ar, this message translates to:
  /// **'شاشة مؤقتة لـ {title}'**
  String lessonTempScreen(Object title);

  /// No description provided for @quizDomainAqeedah.
  ///
  /// In ar, this message translates to:
  /// **'العقيدة'**
  String get quizDomainAqeedah;

  /// No description provided for @quizDomainSkills.
  ///
  /// In ar, this message translates to:
  /// **'مهارات'**
  String get quizDomainSkills;

  /// No description provided for @quizDomainDevelopment.
  ///
  /// In ar, this message translates to:
  /// **'تنمية'**
  String get quizDomainDevelopment;

  /// No description provided for @quizShareMessage.
  ///
  /// In ar, this message translates to:
  /// **'حصلت على {score} من {total} نقطة في اختبار «المربّي» 🤍\n{praise} — جرّب أنت كمان:'**
  String quizShareMessage(Object praise, Object score, Object total);

  /// No description provided for @quizScorePoints.
  ///
  /// In ar, this message translates to:
  /// **'{score} / {total} نقطة'**
  String quizScorePoints(Object score, Object total);

  /// No description provided for @quizTimeSeconds.
  ///
  /// In ar, this message translates to:
  /// **'{seconds} ث'**
  String quizTimeSeconds(Object seconds);

  /// No description provided for @quizPointsCount.
  ///
  /// In ar, this message translates to:
  /// **'{score} نقطة'**
  String quizPointsCount(Object score);

  /// No description provided for @quizQuestionOf.
  ///
  /// In ar, this message translates to:
  /// **'سؤال {current} من {total}'**
  String quizQuestionOf(Object current, Object total);

  /// No description provided for @quizNextQuestion.
  ///
  /// In ar, this message translates to:
  /// **'السؤال التالي'**
  String get quizNextQuestion;

  /// No description provided for @quizShowResult.
  ///
  /// In ar, this message translates to:
  /// **'عرض النتيجة'**
  String get quizShowResult;

  /// No description provided for @quizResultExcellent.
  ///
  /// In ar, this message translates to:
  /// **'ما شاء الله! أداء ممتاز.'**
  String get quizResultExcellent;

  /// No description provided for @quizResultGood.
  ///
  /// In ar, this message translates to:
  /// **'جيد. راجع الدروس التي أخطأت فيها.'**
  String get quizResultGood;

  /// No description provided for @quizResultReview.
  ///
  /// In ar, this message translates to:
  /// **'لا بأس — المراجعة خير من الندم. اقرأ الدرس مرة أخرى.'**
  String get quizResultReview;

  /// No description provided for @quizYourResult.
  ///
  /// In ar, this message translates to:
  /// **'نتيجتك'**
  String get quizYourResult;

  /// No description provided for @quizFallbackTitle.
  ///
  /// In ar, this message translates to:
  /// **'اختبار'**
  String get quizFallbackTitle;

  /// No description provided for @reportScreenTitle.
  ///
  /// In ar, this message translates to:
  /// **'📄 تقرير الدرس'**
  String get reportScreenTitle;

  /// No description provided for @reportLoadError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل التقرير'**
  String get reportLoadError;

  /// No description provided for @dataTableTitle.
  ///
  /// In ar, this message translates to:
  /// **'📋 جدول البيانات'**
  String get dataTableTitle;

  /// No description provided for @dataTableLoadError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الجدول'**
  String get dataTableLoadError;

  /// No description provided for @favoritesRemoveTooltip.
  ///
  /// In ar, this message translates to:
  /// **'إزالة من المفضلة'**
  String get favoritesRemoveTooltip;

  /// No description provided for @searchClearTooltip.
  ///
  /// In ar, this message translates to:
  /// **'مسح'**
  String get searchClearTooltip;

  /// No description provided for @searchTypeLesson.
  ///
  /// In ar, this message translates to:
  /// **'درس'**
  String get searchTypeLesson;

  /// No description provided for @searchTypePath.
  ///
  /// In ar, this message translates to:
  /// **'مسار'**
  String get searchTypePath;

  /// No description provided for @searchTypeTip.
  ///
  /// In ar, this message translates to:
  /// **'نصيحة'**
  String get searchTypeTip;

  /// No description provided for @storyLoadError.
  ///
  /// In ar, this message translates to:
  /// **'تعذر تحميل القصص'**
  String get storyLoadError;

  /// No description provided for @storyEmpty.
  ///
  /// In ar, this message translates to:
  /// **'لا توجد قصص حالياً'**
  String get storyEmpty;

  /// No description provided for @storyEmptyDesc.
  ///
  /// In ar, this message translates to:
  /// **'انتظرونا، سنضيف قصصاً جديدة قريباً!'**
  String get storyEmptyDesc;

  /// No description provided for @storyTapToOpen.
  ///
  /// In ar, this message translates to:
  /// **'اضغط لفتح القصة'**
  String get storyTapToOpen;

  /// No description provided for @storyBedtimeTitle.
  ///
  /// In ar, this message translates to:
  /// **'حكايات قبل النوم 🌙'**
  String get storyBedtimeTitle;

  /// No description provided for @storyWellDone.
  ///
  /// In ar, this message translates to:
  /// **'أحسنت يا بطل!'**
  String get storyWellDone;

  /// No description provided for @storyRelaxNow.
  ///
  /// In ar, this message translates to:
  /// **'استرخِ الآن واغمض عينيك، فالأحلام الجميلة تنتظرك.'**
  String get storyRelaxNow;

  /// No description provided for @storyClose.
  ///
  /// In ar, this message translates to:
  /// **'أغلق القصة'**
  String get storyClose;

  /// No description provided for @videoMinimizeTooltip.
  ///
  /// In ar, this message translates to:
  /// **'تصغير'**
  String get videoMinimizeTooltip;

  /// No description provided for @videoRotateTooltip.
  ///
  /// In ar, this message translates to:
  /// **'تدوير الشاشة'**
  String get videoRotateTooltip;

  /// No description provided for @videoCloseTooltip.
  ///
  /// In ar, this message translates to:
  /// **'إغلاق'**
  String get videoCloseTooltip;

  /// No description provided for @videoFullscreenTooltip.
  ///
  /// In ar, this message translates to:
  /// **'ملء الشاشة'**
  String get videoFullscreenTooltip;

  /// No description provided for @infographicRotateTooltip.
  ///
  /// In ar, this message translates to:
  /// **'تدوير الشاشة'**
  String get infographicRotateTooltip;

  /// No description provided for @infographicDownloadTooltip.
  ///
  /// In ar, this message translates to:
  /// **'تحميل'**
  String get infographicDownloadTooltip;

  /// No description provided for @infographicLoadError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل الإنفوجرافيك'**
  String get infographicLoadError;

  /// No description provided for @podcastUnavailable.
  ///
  /// In ar, this message translates to:
  /// **'البودكاست غير متاح حالياً. سيتاح قريباً بإذن الله.'**
  String get podcastUnavailable;

  /// No description provided for @podcastLoadError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل البودكاست. تأكد من اتصالك بالإنترنت.'**
  String get podcastLoadError;

  /// No description provided for @podcastSpeed.
  ///
  /// In ar, this message translates to:
  /// **'السرعة: {speed}×'**
  String podcastSpeed(Object speed);

  /// No description provided for @activeChildLabel.
  ///
  /// In ar, this message translates to:
  /// **'طفل نشط'**
  String get activeChildLabel;

  /// No description provided for @coachAskAboutTip.
  ///
  /// In ar, this message translates to:
  /// **'اسأل المربّي عن ده'**
  String get coachAskAboutTip;

  /// No description provided for @dailyTipShareError.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر مشاركة النصيحة: {error}'**
  String dailyTipShareError(Object error);

  /// No description provided for @onbChooseAvatar.
  ///
  /// In ar, this message translates to:
  /// **'اختر صورة طفلك'**
  String get onbChooseAvatar;

  /// No description provided for @addChildNameRequired.
  ///
  /// In ar, this message translates to:
  /// **'الاسم مطلوب'**
  String get addChildNameRequired;

  /// No description provided for @addChildNameTooLong.
  ///
  /// In ar, this message translates to:
  /// **'الاسم طويل جداً (الحد الأقصى 80 حرفاً)'**
  String get addChildNameTooLong;

  /// No description provided for @badgesEarnedOf.
  ///
  /// In ar, this message translates to:
  /// **'حصلت على {earned} من {total} إنجازات'**
  String badgesEarnedOf(Object earned, Object total);

  /// No description provided for @badgesEarnedOfShort.
  ///
  /// In ar, this message translates to:
  /// **'حصلت على {earned} من {total}'**
  String badgesEarnedOfShort(Object earned, Object total);

  /// No description provided for @badgeEarnedTapShare.
  ///
  /// In ar, this message translates to:
  /// **'تم الحصول عليه — اضغط للمشاركة'**
  String get badgeEarnedTapShare;

  /// No description provided for @badgeLockedYet.
  ///
  /// In ar, this message translates to:
  /// **'لم يُفتح بعد'**
  String get badgeLockedYet;

  /// No description provided for @identityLinkIncomplete.
  ///
  /// In ar, this message translates to:
  /// **'لم يكتمل ربط الحساب. تحقق من إعداد Google أو جرّب مرة أخرى.'**
  String get identityLinkIncomplete;

  /// No description provided for @identityServerUnreachable.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر الاتصال بالخادم. تحقق من اتصالك بالإنترنت.'**
  String get identityServerUnreachable;

  /// No description provided for @identityLinkFailed.
  ///
  /// In ar, this message translates to:
  /// **'فشل ربط الحساب: {error}'**
  String identityLinkFailed(Object error);

  /// No description provided for @identityLocalNote.
  ///
  /// In ar, this message translates to:
  /// **'البيانات تبقى على نفس الجهاز إلا إذا اخترت تسجيل الدخول.'**
  String get identityLocalNote;

  /// No description provided for @exclusiveBadgeOwned.
  ///
  /// In ar, this message translates to:
  /// **'مملوكة ✓'**
  String get exclusiveBadgeOwned;

  /// No description provided for @reflectionNoteBadge.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظة'**
  String get reflectionNoteBadge;

  /// No description provided for @reflectionMyNotes.
  ///
  /// In ar, this message translates to:
  /// **'ملاحظاتي'**
  String get reflectionMyNotes;

  /// No description provided for @reflectionHint.
  ///
  /// In ar, this message translates to:
  /// **'كيف كانت تجربتك مع هذا الدرس؟ ماذا نجحت؟ ماذا ستجربين غداً؟'**
  String get reflectionHint;

  /// No description provided for @inviteCodeHint.
  ///
  /// In ar, this message translates to:
  /// **'مثال: SMDYVE'**
  String get inviteCodeHint;

  /// No description provided for @celebrationMashallah.
  ///
  /// In ar, this message translates to:
  /// **'ما شاء الله!'**
  String get celebrationMashallah;

  /// No description provided for @quranMemFirstSurahMsg.
  ///
  /// In ar, this message translates to:
  /// **'{name} حفظ أول سورة — سورة {surah} 🌟'**
  String quranMemFirstSurahMsg(Object name, Object surah);

  /// No description provided for @quranMemSurahTile.
  ///
  /// In ar, this message translates to:
  /// **'سورة {name}'**
  String quranMemSurahTile(Object name);

  /// No description provided for @progressCompleted.
  ///
  /// In ar, this message translates to:
  /// **'مكتمل'**
  String get progressCompleted;

  /// No description provided for @progressInProgress.
  ///
  /// In ar, this message translates to:
  /// **'قيد التنفيذ'**
  String get progressInProgress;

  /// No description provided for @progressNotStarted.
  ///
  /// In ar, this message translates to:
  /// **'لم يبدأ'**
  String get progressNotStarted;

  /// No description provided for @backupInvalidFile.
  ///
  /// In ar, this message translates to:
  /// **'ملف النسخ الاحتياطي غير صالح: حقل \"version\" مفقود.'**
  String get backupInvalidFile;

  /// No description provided for @backupNewerVersion.
  ///
  /// In ar, this message translates to:
  /// **'إصدار النسخ الاحتياطي ({version}) أحدث من إصدار التطبيق ({appVersion}). يرجى تحديث التطبيق.'**
  String backupNewerVersion(Object appVersion, Object version);

  /// No description provided for @backupInvalidJson.
  ///
  /// In ar, this message translates to:
  /// **'ملف JSON غير صالح: {error}'**
  String backupInvalidJson(Object error);

  /// No description provided for @backupUnexpectedError.
  ///
  /// In ar, this message translates to:
  /// **'حدث خطأ غير متوقع: {error}'**
  String backupUnexpectedError(Object error);

  /// No description provided for @reviewPromptTitle.
  ///
  /// In ar, this message translates to:
  /// **'هل أعجبك «المربّي»؟ 🌟'**
  String get reviewPromptTitle;

  /// No description provided for @reviewPromptBody.
  ///
  /// In ar, this message translates to:
  /// **'تقييمك على المتجر يساعد آباءً غيرك يجدون التطبيق — وفي ميزان حسناتك إن شاء الله.'**
  String get reviewPromptBody;

  /// No description provided for @reviewPromptLater.
  ///
  /// In ar, this message translates to:
  /// **'لاحقًا'**
  String get reviewPromptLater;

  /// No description provided for @reviewPromptNow.
  ///
  /// In ar, this message translates to:
  /// **'قيّم الآن'**
  String get reviewPromptNow;

  /// No description provided for @bedtimeAdhkarCounter.
  ///
  /// In ar, this message translates to:
  /// **'الذكر {current} من {total}'**
  String bedtimeAdhkarCounter(Object current, Object total);

  /// No description provided for @bedtimeTapToRepeat.
  ///
  /// In ar, this message translates to:
  /// **'اضغط هنا للتكرار: {count}'**
  String bedtimeTapToRepeat(Object count);

  /// No description provided for @tourNext.
  ///
  /// In ar, this message translates to:
  /// **'التالي'**
  String get tourNext;

  /// No description provided for @tourSkip.
  ///
  /// In ar, this message translates to:
  /// **'تخطّي'**
  String get tourSkip;

  /// No description provided for @tourDone.
  ///
  /// In ar, this message translates to:
  /// **'تمام'**
  String get tourDone;

  /// No description provided for @tourTodayTitle.
  ///
  /// In ar, this message translates to:
  /// **'اليوم'**
  String get tourTodayTitle;

  /// No description provided for @tourTodayBody.
  ///
  /// In ar, this message translates to:
  /// **'من هنا يبدأ يومك.'**
  String get tourTodayBody;

  /// No description provided for @tourLearnTitle.
  ///
  /// In ar, this message translates to:
  /// **'التعلّم'**
  String get tourLearnTitle;

  /// No description provided for @tourLearnBody.
  ///
  /// In ar, this message translates to:
  /// **'المسارات والدروس كلّها هنا.'**
  String get tourLearnBody;

  /// No description provided for @tourAssistantTitle.
  ///
  /// In ar, this message translates to:
  /// **'المساعد'**
  String get tourAssistantTitle;

  /// No description provided for @tourAssistantBody.
  ///
  /// In ar, this message translates to:
  /// **'اسأل في أي وقت، ونحن معك.'**
  String get tourAssistantBody;

  /// No description provided for @tourMoreTitle.
  ///
  /// In ar, this message translates to:
  /// **'المزيد'**
  String get tourMoreTitle;

  /// No description provided for @tourMoreBody.
  ///
  /// In ar, this message translates to:
  /// **'كل شيء آخر تلاقيه هنا.'**
  String get tourMoreBody;

  /// No description provided for @tourFocusTitle.
  ///
  /// In ar, this message translates to:
  /// **'خطوتك التالية'**
  String get tourFocusTitle;

  /// No description provided for @tourFocusBody.
  ///
  /// In ar, this message translates to:
  /// **'خطوتك التالية دائمًا هنا.'**
  String get tourFocusBody;

  /// No description provided for @tourReplay.
  ///
  /// In ar, this message translates to:
  /// **'الجولة التعريفية'**
  String get tourReplay;

  /// No description provided for @tourReplayDesc.
  ///
  /// In ar, this message translates to:
  /// **'أعِد عرض الجولة عند العودة للشاشة الرئيسية'**
  String get tourReplayDesc;

  /// No description provided for @tourReplayQueued.
  ///
  /// In ar, this message translates to:
  /// **'الجولة هتظهر لما ترجع للشاشة الرئيسية.'**
  String get tourReplayQueued;

  /// No description provided for @errorOfflineTitle.
  ///
  /// In ar, this message translates to:
  /// **'لا يوجد اتصال بالإنترنت'**
  String get errorOfflineTitle;

  /// No description provided for @errorOfflineBody.
  ///
  /// In ar, this message translates to:
  /// **'تأكّد من اتصالك وحاول مرة أخرى.'**
  String get errorOfflineBody;

  /// No description provided for @errorServerTitle.
  ///
  /// In ar, this message translates to:
  /// **'الخدمة لا تستجيب الآن'**
  String get errorServerTitle;

  /// No description provided for @errorServerBody.
  ///
  /// In ar, this message translates to:
  /// **'المشكلة من عندنا لا من عندك. حاول بعد قليل.'**
  String get errorServerBody;

  /// No description provided for @errorUnknownTitle.
  ///
  /// In ar, this message translates to:
  /// **'تعذّر تحميل البيانات'**
  String get errorUnknownTitle;

  /// No description provided for @errorUnknownBody.
  ///
  /// In ar, this message translates to:
  /// **'حاول مرة أخرى، وإن تكرّر الأمر أرسل لنا ملاحظة.'**
  String get errorUnknownBody;
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
