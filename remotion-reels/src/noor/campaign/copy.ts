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
	stations: [
		{n: '١', title: 'خطوة اليوم', sub: 'درس في دقائق'}, // app: noorChipStep
		{n: '٢', title: 'اسأل المربّي', sub: 'عن أي موقف مع طفلك'}, // app: todayAskTitle
		{n: '٣', title: 'مهمة الطفل', sub: 'مهمة صغيرة له اليوم'}, // app: todayMissionTitleNoName
	],
	message: ['ثلاث خطوات صغيرة…', 'كل يوم'],
	tagline: 'درب واضح لكل يوم',
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
	yourTurn: ['يا يوسف،', 'دورك الآن'], // app: handoverYourTurn
	missionLabel: 'مهمتك الآن',
	mission: ['اسقِ النبتة،', 'ثم عُد إلينا'],
	done: 'تمّت',
	giveBack: ['أعِد الجهاز إلى أهلك', 'شكرًا لك'], // app: childReturnDevice
	message: ['وقت شاشة له هدف…', 'وبرمز يحميه'],
	tagline: 'وقت شاشة له هدف',
};

export const V5 = {
	hook: ['رمضان هذا العام…', 'مختلف'],
	moments: ['قصة معًا قبل النوم', 'مائدة الإفطار… بأيدينا', 'زيارة للجدّة', 'هدية صغيرة للجيران'],
	dayByDay: 'ويومًا بعد يوم…',
	message: ['رمضان عائلي…', 'خطوة بخطوة'],
	tagline: 'رمضان عائلي… خطوة بخطوة',
};
