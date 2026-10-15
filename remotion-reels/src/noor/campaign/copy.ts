// On-screen words of the five campaign reels, in one place for review.
// Easy Modern Standard Arabic (not dialect), family-neutral, no promises of
// reward, and no verses, hadith or supplications quoted anywhere. Strings
// that are the app's own words are marked «app»: they match
// mobile/lib/l10n/app_ar.arb so the reel shows what the app really says.

export const END = {
	title: 'المربّي',
	free: 'مجاني لوجه الله — بلا إعلانات',
	play: 'متاح على Google Play',
	scan: 'امسح للتنزيل',
};

export const V1 = {
	hook: ['نصيحة سمعتها…', 'ونسيتها؟'],
	label: 'خطوة اليوم', // app: noorChipStep
	step: ['قبل النوم، اسأل مريم:', 'ما أجمل لحظة في يومك؟'],
	when: 'متى ستجرّبها مع مريم؟', // app: promiseWhenTitle
	options: ['الليلة', 'غدًا', 'هذا الأسبوع'], // app: promiseTonight / promiseTomorrow / promiseThisWeek
	nextDay: 'في اليوم التالي…',
	followup: ['جرّبتها مع مريم؟', 'كيف جرت؟'],
	outcomes: ['نجحت', 'نجحت جزئيًا', 'لم تنجح', 'لم أجرّب بعد'], // app: followupWorked … followupDidntTry
	thanks: 'الحمد لله، نفعت!', // app: followupThanksWorked
	message: ['مربٍّ يتذكّر معك'],
	tagline: 'مربٍّ يتذكّر معك',
};

export const V2 = {
	hook: ['لا تعرف', 'من أين تبدأ؟'],
	topics: ['النوم', 'العناد', 'الشاشات', 'الغضب', 'الطعام', 'الدراسة'],
	// «درب {الاسم}» (#130) — the app's own words
	title: 'درب مريم', // app: familyRoadTitle
	horizon: 'على الأفق', // app: familyRoadHorizon
	// far … near, top to bottom, as the screen lists them
	gates: [
		{title: 'سنّ السابعة', line: 'تبدأ رحلة الصلاة هنا، خطوة بعد خطوة.', action: ''}, // app: gateAgeSeven / gateAgeSevenNote
		{title: 'رمضان', line: '', action: 'برنامج رمضان'}, // app: gateRamadan / noorChipRamadan
		{eyebrow: 'المسار التالي', title: 'بذور العقيدة: أول تعريف بالله', line: '', action: 'افتح المسار'}, // app: gateNextPath / gateOpenPath
	] as {eyebrow?: string; title: string; line: string; action: string}[],
	here: 'أنتم هنا', // app: familyRoadHere
	hereHint: 'كل خطوة تربوية تضيء قنديلًا على هذا الدرب.', // app: familyRoadHereHint
	lit: 'ما أضأتموه', // app: familyRoadLit
	thisWeek: 'هذا الأسبوع', // app: familyRoadThisWeek
	start: 'من هنا بدأ دربكم', // app: familyRoadStart
	message: ['ما أضأتموه…', 'وما ينتظركم'],
	tagline: 'درب أسرتكم… خطوة بخطوة',
};

export const V3 = {
	label: 'اسأل المربّي', // app: todayAskTitle
	question: 'طفلي يعاند وقت النوم… ماذا أفعل؟',
	age: 'لعمر ٤ سنوات',
	// one array per step, one string per line
	steps: [['روتين ثابت كل ليلة:', 'حمّام، ثم قصة، ثم نوم.'], ['نبّهه قبل النوم بعشر دقائق.'], ['خيّره بين قصتين:', 'أيّهما نقرأ الليلة؟']],
	calm: 'وابقَ هادئًا… فالثبات أنفع من الجدال.',
	button: 'سأجرّبها',
	message: ['إجابة تعرف', 'عمر طفلك'],
	tagline: 'إجابة تعرف عمر طفلك',
};

export const V4 = {
	hook: ['الشاشة…', 'بنيّة.'],
	gate: 'تسليم الجهاز', // app: handoverTitle
	pin: 'أدخل الرمز',
	// «ركن الطفل» (#129), a 4–6 child: a story, then the task (no game at this age)
	greeting: 'يا عمر، هذا ركنك', // app: childCornerGreeting
	candleLabel: 'شمعة وقتك', // app: childCornerCandleLabel
	candleBright: 'ما زالت مضيئة', // app: childCornerCandleBright
	noorLine: 'هنا حكاية قصيرة، ثم مهمة صغيرة بعيدًا عن الشاشة.', // app: childCornerNoorLineNoGame
	storyLabel: 'حكاية', // app: childCornerStoryLabel
	storyTitle: 'يوسف وغرسة الأمل', // the stories library (hope_sprout)
	storyHint: 'نقرؤها معًا', // app: childCornerStoryHint
	missionLabel: 'ثم مهمتك', // app: childCornerMissionLabel
	toMission: 'إلى مهمتي', // app: childCornerToMission
	storyText: 'يوسف ولد طيب يحب الطبيعة ومساعدة والديه. في صباح يوم مشرق، أعطاه والده بذرة صغيرة ذهبية اللون.', // hope_sprout p.1
	next: 'التالي', // app: childCornerStoryNext
	missionNow: 'مهمتك الآن', // app: childCornerMissionNow
	missionTitle: 'صيّاد الألوان', // child_missions: mission_4-6_color_hunt
	missionBody: 'ابحث في البيت عن ثلاثة أشياء حمراء وثلاثة زرقاء، ثم رتّبها على الطاولة واحكِ لأمك أو أبيك ما وجدت.',
	missionGo: 'فهمت، سأذهب إليها', // app: childCornerMissionGo
	giveBack: ['أعِد الجهاز إلى أهلك', 'شكرًا لك'], // app: childReturnDevice
	exitPin: 'أدخل الرمز للخروج من وضع الطفل.', // app: childModePinExitSubtitle
	message: ['حكاية، ثم مهمة…', 'بعيدًا عن الشاشة'],
	tagline: 'ركن لطفلك… وقت له نهاية',
};

export const V5 = {
	hook: ['رمضان هذا العام…', 'مختلف'],
	moments: ['قصة معًا قبل النوم', 'مائدة الإفطار… بأيدينا', 'زيارة للجدّة', 'هدية صغيرة للجيران'],
	dayByDay: 'ويومًا بعد يوم…',
	message: ['رمضان عائلي…', 'خطوة بخطوة'],
	tagline: 'رمضان عائلي… خطوة بخطوة',
};

export const V6 = {
	hook: ['حكاية قبل النوم…', 'يرويها نور'],
	intro: 'أنا نور، وهذه حكايتنا الليلة.', // app: storyNoorIntro
	title: 'يوسف وغرسة الأمل', // the stories library (hope_sprout), #126
	// pages 1 and 2 of the story, as the app shows them (first sentences)
	pages: [
		'يوسف ولد طيب يحب الطبيعة ومساعدة والديه. في صباح يوم مشرق، أعطاه والده بذرة صغيرة ذهبية اللون.',
		'حفر يوسف في الأرض برفق ووضع البذرة، ثم غطاها بالتراب وسقاها بماء عذب.',
	],
	pageOf: (n: number, total: number) => `صفحة ${n} من ${total}`, // app: storyPageOf
	pauseTitle: 'وقفة مع نور', // app: storyPauseTitle
	question: 'لو كنت مكان يوسف ولم تنبت البذرة بعد، ماذا ستفعل؟', // hope_sprout pause
	options: ['أصبر وأستمر في سقايتها', 'أتركها وأذهب للعب'],
	affirm: 'صبرك جميل! الزرع يحتاج وقتًا ورعاية، تمامًا مثل غرسة يوسف.',
	continue: 'نكمل الحكاية', // app: storyContinue
	message: ['سؤال صغير…', 'وحديث بينكما'],
	tagline: 'حكاية الليلة… مع نور',
};
