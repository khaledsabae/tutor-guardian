#!/usr/bin/env python3
"""Generate 30 knowledge unit JSON files for Tutor Guardian."""
import json
import os

DATA_DIR = "/home/khalednew/projects/tutor-guardian/knowledge_base/data"
os.makedirs(DATA_DIR, exist_ok=True)

# Clear old files
for f in os.listdir(DATA_DIR):
    if f.endswith('.json'):
        os.remove(os.path.join(DATA_DIR, f))

COUNTER = {"medical": 1, "tarbiyah": 1, "fiqh": 1, "cyber": 1}

def make_unit(domain, age_group, behavior_type, intervention_type, severity,
              reference_type, reference_info, text_original, text_simplified,
              labels, source_title, source_author, source_year):
    n = COUNTER[domain]
    COUNTER[domain] += 1
    uid = f"{domain[:3]}-{n:03d}"
    ts = "2025-06-05T10:00:00Z"
    obj = {
        "id": uid,
        "domain": domain,
        "age_group": age_group,
        "behavior_type": behavior_type,
        "intervention_type": intervention_type,
        "severity": severity,
        "reference_type": reference_type,
        "reference_info": reference_info,
        "text_original": text_original,
        "text_simplified": text_simplified,
        "labels": labels,
        "created_at": ts,
        "updated_at": ts,
        "version": "1.0.0",
        "source_meta": {
            "source_title": source_title,
            "source_author": source_author,
            "source_year": source_year
        }
    }
    path = os.path.join(DATA_DIR, f"{uid}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    print(f"  [OK] {uid} — {behavior_type}")

# ============================================================
# MEDICAL — 8 units
# ============================================================
make_unit("medical", "0-3", "تأخر الكلام", "إرشادي", "متوسط",
    "DSM-5",
    "DSM-5-TR, Communication Disorders, pp. 48-55.",
    "Speech Sound Disorder and Language Disorder are characterized by persistent difficulties in the acquisition and use of language.",
    "إذا كان طفلك في عمر سنتين ولا ينطق كلمات واضحة، لا تقلقي فورًا. تحدثي مع طفلك كثيرًا، اقرئي له قصصًا يوميًا. تجنبي الشاشات قبل السنتين. إذا استمر حتى 3 سنوات، استشيري أخصائي تخاطب.",
    ["تأخر_كلام", "نطق", "طفولة_مبكرة"], "DSM-5-TR", "American Psychiatric Association", 2022)

make_unit("medical", "4-6", "قلق الانفصال", "إرشادي", "متوسط",
    "DSM-5",
    "DSM-5-TR, Anxiety Disorders, pp. 217-221.",
    "Separation Anxiety Disorder involves excessive fear concerning separation from attachment figures.",
    "تمسك طفلك بكِ عند الذهاب للحضانة طبيعي. لا تسخري من خوفه. حضّريه نفسيًا قبل الذهاب بيوم، ودعيه يأخذ لعبته المفضلة. غادري بثقة دون تردد — ترددك يزيد قلقه.",
    ["قلق_انفصال", "حضانة", "خوف"], "DSM-5-TR", "American Psychiatric Association", 2022)

make_unit("medical", "7-9", "تبول لا إرادي ليلي", "إرشادي", "خفيف",
    "DSM-5",
    "DSM-5-TR, Elimination Disorders, pp. 401-406.",
    "Enuresis is repeated voiding of urine into bed or clothes in a child at least 5 years.",
    "التبول الليلي بعد سن الخامسة شائع. لا تعاقبي طفلك ولا تحرجيه. قللي السوائل قبل النوم بساعتين. استخدمي المكافآت عند الليالي الجافة. إذا استمر بعد 7 سنوات، راجعي طبيب أطفال.",
    ["تبول_ليلي", "نوم", "تدريب_حمام"], "DSM-5-TR", "American Psychiatric Association", 2022)

make_unit("medical", "7-9", "اضطراب التحدي المعارض", "علاجي", "متوسط",
    "DSM-5",
    "DSM-5-TR, Disruptive Disorders, ODD, pp. 532-538.",
    "Oppositional Defiant Disorder is a pattern of angry mood, argumentative behavior lasting at least 6 months.",
    "ضعي قواعد واضحة وثابتة في المنزل، وتجنبي الصراخ. استخدمي أسلوب 'الاختيار بين خيارين' بدل الأوامر. كافئي السلوك الإيجابي فورًا. استشيري أخصائيًا نفسيًا سلوكيًا إذا استمر.",
    ["تحدي_معارض", "عناد", "سلوك"], "DSM-5-TR", "American Psychiatric Association", 2022)

make_unit("medical", "10-12", "الاكتئاب عند الأطفال", "إحالة_لطبيب", "شديد",
    "DSM-5",
    "DSM-5-TR, Depressive Disorders, pp. 177-214.",
    "Major Depressive Disorder in children may present with irritable mood, loss of interest, fatigue.",
    "إذا لاحظتِ حزنًا مستمرًا لأكثر من أسبوعين، فقدان الاهتمام، عزلة، تغير الشهية أو النوم — هذه علامات تحذيرية. لا تقولي 'أنت كبير على الحزن'. استشيري فورًا طبيبًا نفسيًا للأطفال.",
    ["اكتئاب", "حزن", "عزلة", "صحة_نفسية"], "DSM-5-TR", "American Psychiatric Association", 2022)

make_unit("medical", "13-15", "اضطرابات الأكل", "علاجي", "شديد",
    "DSM-5",
    "DSM-5-TR, Feeding and Eating Disorders, pp. 371-398.",
    "Anorexia Nervosa involves restriction of energy intake, intense fear of gaining weight.",
    "رفض ابنك للطعام أو هوس النحافة ليس 'موضة'. لا تراقبي أكله أمام الجميع. تحدثي معه بهدوء عن مشاعره وليس شكله. اتصلي بطبيب نفسي متخصص — التأخير خطير.",
    ["اضطرابات_أكل", "نحافة", "مراهقة"], "DSM-5-TR", "American Psychiatric Association", 2022)

make_unit("medical", "13-15", "اضطراب القلق الاجتماعي", "إرشادي", "متوسط",
    "DSM-5",
    "DSM-5-TR, Anxiety Disorders, pp. 229-235.",
    "Social Anxiety Disorder is marked by fear about social situations and scrutiny by others.",
    "إذا كان ابنك المراهق يرتجف عند التحدث أمام زملائه أو يتجنب المناسبات: لا تجبريه على المواجهة المفاجئة. درّجيه في مهارات اجتماعية بسيطة مع أبناء العائلة أولًا. شجّعي هواياته.",
    ["قلق_اجتماعي", "خجل", "مراهقة"], "DSM-5-TR", "American Psychiatric Association", 2022)

make_unit("medical", "16-18", "إيذاء الذات", "إحالة_لطبيب", "طارئ",
    "DSM-5",
    "DSM-5-TR, Non-Suicidal Self-Injury, pp. 920-925.",
    "Non-Suicidal Self-Injury refers to intentional self-inflicted damage to the body without suicidal intent.",
    "اكتشاف أن ابنك يؤذي جسده صدمة. لا تصرخي ولا تعاقبي — هذا ألم نفسي عميق. استمعي له دون حكم. أزيلي الأدوات الحادة. اتصلي فورًا بطبيب نفسي — هذا طارئ.",
    ["إيذاء_ذات", "جرح", "مراهقة", "طارئ"], "DSM-5-TR", "American Psychiatric Association", 2022)

# ============================================================
# TARBIYAH — 8 units
# ============================================================
make_unit("tarbiyah", "0-3", "نوبات غضب", "إرشادي", "خفيف",
    "كتاب_تربوي",
    "د. مصطفى أبو سعد، 'التربية الإيجابية'، ص 45-60.",
    "Toddler tantrums are a normal developmental phase caused by frustration when a child cannot express needs verbally.",
    "نوبات الغضب طبيعية في هذه السن. حافظي على هدوئك — صراخك يزيد الموقف سوءًا. احتضني طفلك بهدوء أو تجاهلي النوبة بأمان. لا ترضخي لمطالبه أثناء النوبة. بعد أن يهدأ، تحدثي معه بلغة بسيطة.",
    ["نوبات_غضب", "طفولة_مبكرة", "تربية_إيجابية"], "التربية الإيجابية", "د. مصطفى أبو سعد", 2018)

make_unit("tarbiyah", "4-6", "الكذب عند الأطفال", "إرشادي", "خفيف",
    "كتاب_تربوي",
    "د. عبد الله السبيعي، 'تربية الطفل في الإسلام'، ص 112-130.",
    "Young children often blur fantasy and reality; their 'lies' are frequently wish-fulfillment or fear of punishment.",
    "لا تصفي طفلك بـ 'كذاب' — هذا يرسّخ الصفة. اسأليه بهدوء: 'ماذا حدث حقًا؟' دون تهديد. امدحي الصدق عندما يقوله. القصص التربوية عن فضيلة الصدق أكثر تأثيرًا من العقاب.",
    ["كذب", "صدق", "تربية_أخلاقية"], "تربية الطفل في الإسلام", "د. عبد الله السبيعي", 2015)

make_unit("tarbiyah", "7-9", "التنمر المدرسي", "إرشادي", "متوسط",
    "كتاب_تربوي",
    "د. جاسم المطوع، 'كيف نحمي أبناءنا من التنمر'، ص 30-55.",
    "School bullying includes physical aggression, verbal insults, and social exclusion, affecting 1 in 3 students globally (UNESCO 2019).",
    "إذا اشتكى طفلك من التنمر: استمعي له بجدية ولا تقولي 'دافع عن نفسك' فقط. بلّغي إدارة المدرسة رسميًا. علّميه عبارات بسيطة وحازمة: 'توقف، هذا لا يعجبني'. عزّزي ثقته في البيت. لا تعلّميه الانتقام الجسدي.",
    ["تنمر", "مدرسة", "ثقة_بالنفس", "حماية"], "كيف نحمي أبناءنا من التنمر", "د. جاسم المطوع", 2020)

make_unit("tarbiyah", "7-9", "التعليم باللعب", "وقائي", "خفيف",
    "كتاب_تربوي",
    "ماريا مونتيسوري، 'العقل المستوعب'، فصل 6.",
    "Play is the work of the child. Through play, children develop cognitive, social, and emotional skills naturally.",
    "اللعب ليس 'تضييع وقت' — إنه أداة التعلم الأقوى في هذه السن. استخدمي الألعاب لتعليم الحساب (المكعبات) والقراءة (بطاقات الصور). اجعلي وقت الواجب مرحًا لا معركة. الطفل الذي يتعلم بلعب يحب المدرسة لاحقًا.",
    ["لعب", "تعليم", "مونتيسوري", "طفولة"], "العقل المستوعب", "ماريا مونتيسوري", 1949)

make_unit("tarbiyah", "10-12", "التربية الجنسية للأطفال", "وقائي", "متوسط",
    "كتاب_تربوي",
    "د. ليلى الهاشمي، 'التربية الجنسية في الإسلام'، ص 70-95.",
    "Age-appropriate sexuality education helps children understand body safety, boundaries, and healthy relationships.",
    "لا تنتظري حتى البلوغ. في هذا العمر يحتاج الطفل أن يعرف: أسماء أعضاء جسمه الصحيحة، الفرق بين اللمسة الآمنة وغير الآمنة، أن جسده ملكه ولا يحق لأحد لمسه دون إذنه. أجيبي على أسئلته بصدق وبساطة حسب عمره.",
    ["تربية_جنسية", "حماية_جسدية", "حدود"], "التربية الجنسية في الإسلام", "د. ليلى الهاشمي", 2019)

make_unit("tarbiyah", "13-15", "صراع الهوية عند المراهق", "إرشادي", "متوسط",
    "كتاب_تربوي",
    "د. أكرم رضا، 'مراهقون بلا أزمات'، ص 88-110.",
    "Adolescent identity formation involves questioning values, experimenting with roles, and seeking autonomy.",
    "تمرد ابنك المراهق ليس حربًا عليك — إنه بحث عن ذاته. استمعي له أكثر مما تتحدثين. ناقشي ولا تفرضي. اسمحي له باتخاذ قرارات صغيرة ليكتسب الثقة. ركّزي على القيم الكبرى وتغاضي عن الخلافات الصغيرة (قصة الشعر، لون الحذاء).",
    ["هوية", "مراهقة", "تمرد", "حوار"], "مراهقون بلا أزمات", "د. أكرم رضا", 2017)

make_unit("tarbiyah", "16-18", "اختيار التخصص الدراسي", "إرشادي", "خفيف",
    "كتاب_تربوي",
    "د. محمد المطيري، 'دليل الأسرة في توجيه الأبناء أكاديميًا'، ص 140-165.",
    "Career guidance for adolescents should balance aptitude, interest, and labor market realities.",
    "لا تفرضي تخصصًا على ابنك لأنه 'حلم حياتك'. اكتشفي ميوله وقدراته: ماذا يحب أن يفعل في وقت فراغه؟ ما المواد التي يتفوق فيها؟ خذيه لزيارات ميدانية للمهن المختلفة. اسأليه: 'كيف تتخيل يومك بعد 10 سنوات؟' بدل 'أدخل طب!'",
    ["تخصص", "جامعة", "مستقبل_مهني"], "دليل الأسرة في توجيه الأبناء", "د. محمد المطيري", 2021)

make_unit("tarbiyah", "16-18", "الاستعداد للزواج المبكر", "وقائي", "خفيف",
    "كتاب_تربوي",
    "د. خالد الراشد، 'الأسرة المسلمة: تأسيس ورعاية'، ص 20-45.",
    "Premarital education includes communication skills, conflict resolution, financial planning, and realistic expectations.",
    "لا تخجلي من فتح موضوع الزواج مع ابنك/ابنتك. ناقشيهم في: معايير اختيار الشريك، مهارات التواصل وحل الخلافات، المسؤوليات المالية والمنزلية. الزواج الناجح يحتاج وعيًا لا حبًا فقط. كوني صريحة — أخطاؤك دروس لهم.",
    ["زواج", "أسرة", "توعية"], "الأسرة المسلمة", "د. خالد الراشد", 2016)

# ============================================================
# FIQH — 7 units
# ============================================================
make_unit("fiqh", "4-6", "تحفيظ القرآن للأطفال", "إرشادي", "خفيف",
    "كتاب_فقهي",
    "ابن كثير، 'فضائل القرآن'، باب تعليم الصغار.",
    "The Prophet (PBUH) said: 'The best among you are those who learn the Quran and teach it.' (Bukhari 5027).",
    "ابدئي بالسور القصيرة التي يحبها (الإخلاص، الفلق، الناس). التكرار اليومي مع اللحن والتجويد الجماعي. اربطي الحفظ بمكافآت بسيطة (ملصقات، قصص). الهدف في هذه السن: حب القرآن وليس كمال الحفظ. لا تضربي ولا تجبري.",
    ["قرآن", "تحفيظ", "طفولة"], "فضائل القرآن", "ابن كثير", 1373)

make_unit("fiqh", "7-9", "آداب الطعام والشراب", "وقائي", "خفيف",
    "حديث",
    "صحيح البخاري، كتاب الأطعمة، حديث 5376.",
    "The Prophet (PBUH) said: 'O boy, say Bismillah, eat with your right hand, and eat from what is in front of you.' (Bukhari 5376).",
    "علّمي طفلك آداب الطعام منذ الصغر: التسمية قبل الأكل، الأكل باليد اليمنى، الأكل مما يليه، وحمد الله بعد الانتهاء. القدوة أهم من التعليم النظري — اجلسي معه على مائدة واحدة وأريه بنفسك. لا توبخيه على الأخطاء بل ذكّريه بلطف.",
    ["آداب", "طعام", "حديث", "أخلاق"], "صحيح البخاري", "الإمام البخاري", 846)

make_unit("fiqh", "7-9", "تعليم الصيام للأطفال", "إرشادي", "خفيف",
    "كتاب_فقهي",
    "النووي، 'المجموع شرح المهذب'، كتاب الصيام.",
    "Scholars recommend gradual training of children for fasting, such as fasting until midday initially.",
    "الصيام للأطفال تدريجي: ابدئي بصيام بضع ساعات، ثم حتى الظهر، ثم يومًا كاملًا عند القدرة. اجعلي السحور أسريًا ممتعًا. امدحي صبره ولا تأنبيه إن أفطر. الصيام قبل البلوغ تدريب لا فرض — كافئيه على المحاولة لا النتيجة.",
    ["صيام", "رمضان", "تدريب", "عبادة"], "المجموع شرح المهذب", "الإمام النووي", 1270)

make_unit("fiqh", "10-12", "الحياء واللباس الشرعي", "وقائي", "خفيف",
    "كتاب_فقهي",
    "ابن حجر العسقلاني، 'فتح الباري'، كتاب اللباس.",
    "The Prophet (PBUH) said: 'Modesty is part of faith.' (Bukhari 24).",
    "علّمي ابنك/ابنتك مفهوم الحياء كقيمة إسلامية قبل أن يكون 'زيًا'. اشرحي الحكمة من الحجاب للبنت بالتدريج لا بالأوامر. للولد: غض البصر واحترام خصوصية الآخرين. الأهم: كوني قدوة في حيائك قبل لباسك.",
    ["حياء", "لباس", "حجاب", "أخلاق"], "فتح الباري", "ابن حجر العسقلاني", 1449)

make_unit("fiqh", "13-15", "التعامل مع الشبهات الفكرية", "إرشادي", "متوسط",
    "كتاب_فقهي",
    "ابن تيمية، 'درء تعارض العقل والنقل'، المجلد الأول.",
    "Islamic creed education should equip youth to face intellectual doubts with knowledge and critical thinking.",
    "إذا طرح ابنك المراهق أسئلة وجودية أو شبهات عن الدين، لا تصرخي ولا تمنعيه من السؤال. اسأليه: 'ماذا قرأت؟' باهتمام. ابحثي معه عن الإجابة عند عالم موثوق. السؤال دليل عقل وليس دليل كفر. جهّليه فكريًا لا عاطفيًا فقط.",
    ["شبهات", "إيمان", "مراهقة", "فكر"], "درء تعارض العقل والنقل", "ابن تيمية", 1315)

make_unit("fiqh", "13-15", "أحكام البلوغ والطهارة", "وقائي", "خفيف",
    "كتاب_فقهي",
    "النووي، 'المجموع شرح المهذب'، كتاب الطهارة.",
    "Islamic jurisprudence on puberty includes rulings on ritual purity, prayer, and fasting obligations.",
    "بلّغي ابنك/ابنتك أحكام البلوغ قبل حدوثه بسنة على الأقل: علامات البلوغ، الطهارة والاغتسال، الصلاة والصيام كفرض، وآداب التعامل مع الجنس الآخر. الحديث المبكر الهادئ يمنع الصدمة والخجل. الأم للبنت والأب للابن أفضل إن أمكن.",
    ["بلوغ", "طهارة", "فقه"], "المجموع شرح المهذب", "الإمام النووي", 1270)

make_unit("fiqh", "16-18", "فقه العلاقات قبل الزواج", "وقائي", "خفيف",
    "كتاب_فقهي",
    "يوسف القرضاوي، 'فتاوى معاصرة'، المجلد الثالث.",
    "Islamic rulings on gender relations emphasize modesty, avoiding seclusion (khalwa), and purposeful interaction.",
    "ناقشي ابنك/ابنتك بصراحة حول: حدود العلاقة مع الجنس الآخر في الإسلام، مفهوم الخلوة المحرمة، ضوابط الخطوبة الشرعية، والفرق بين الحب والزواج. كوني مرجعهم الآمن — إذا لم يجدوا الإجابة عندك، سيبحثون عنها في مكان آخر.",
    ["علاقات", "خطوبة", "شرع", "شباب"], "فتاوى معاصرة", "يوسف القرضاوي", 2005)

# ============================================================
# CYBER — 7 units
# ============================================================
make_unit("cyber", "4-6", "وقت الشاشة للأطفال الصغار", "وقائي", "خفيف",
    "تقرير_سيبراني",
    "American Academy of Pediatrics, 'Media and Young Minds', Pediatrics 2016.",
    "AAP recommends no screen time for children under 18 months, and 1 hour/day of high-quality content for ages 2-5.",
    "لا شاشات قبل 18 شهرًا. بين 2-5 سنوات: ساعة واحدة يوميًا من المحتوى الهادف فقط، وبحضورك. لا تجعلي التلفزيون 'جليسة أطفال'. الأفضل: مكعبات، تلوين، قصص ورقية. عقل طفلك ينمو بالتفاعل البشري لا بالشاشات.",
    ["شاشات", "طفولة_مبكرة", "وقت_رقمي"], "Media and Young Minds", "American Academy of Pediatrics", 2016)

make_unit("cyber", "7-9", "حماية الطفل من المحتوى غير المناسب", "وقائي", "متوسط",
    "تقرير_سيبراني",
    "Internet Watch Foundation (IWF), 'Online Safety for Parents', 2023.",
    "Parental controls and safe search settings can reduce but not eliminate exposure to inappropriate content.",
    "فعّلي خاصية 'البحث الآمن' على يوتيوب وجوجل. استخدمي تطبيقات الرقابة الأبوية (مثل Google Family Link). ضعي الجهاز في مكان مفتوح بالمنزل — ليس في غرفة الطفل. أخبري طفلك: 'إذا رأيت شيئًا يزعجك على الشاشة، تعالَ أخبرني فورًا ولن أعاقبك.'",
    ["حماية", "محتوى_غير_مناسب", "رقابة_أبوية"], "Online Safety for Parents", "Internet Watch Foundation", 2023)

make_unit("cyber", "7-9", "التنمر الإلكتروني", "إرشادي", "متوسط",
    "تقرير_سيبراني",
    "UNESCO, 'Behind the Numbers: Ending School Violence and Bullying', 2019.",
    "Cyberbullying involves using digital platforms to harass, threaten, or humiliate peers, affecting mental health.",
    "إذا تعرض طفلك للتنمر الإلكتروني: لا تلوميه ولا تسحبي منه الجهاز كعقاب — هذا يعزله أكثر. خذي لقطات شاشة للأدلة. بلّغي إدارة المدرسة والمنصة. علّميه ألا يرد على المتنمر — الرد يزيد الهجمات. طمئنيه: 'لست وحدك، وأنا معك.'",
    ["تنمر_إلكتروني", "حماية", "مدرسة"], "Behind the Numbers", "UNESCO", 2019)

make_unit("cyber", "10-12", "إدمان الألعاب الإلكترونية", "وقائي", "متوسط",
    "تقرير_سيبراني",
    "WHO ICD-11, Gaming Disorder; AAP Family Media Plan, 2020.",
    "Gaming disorder is a pattern of gaming behavior with impaired control and increasing priority over daily activities.",
    "لا تقطعي الألعاب فجأة. حددي وقتًا يوميًا متفقًا عليه (مثل ساعة بعد الواجبات). الأجهزة في مكان مشترك لا في غرفة النوم. شاركي طفلك اللعب أحيانًا لتفهمي محتواه. قدّمي بدائل: رياضة، ألعاب عائلية. الهدف توازن لا حرمان.",
    ["ألعاب", "إدمان_رقمي", "توازن"], "ICD-11 / AAP Family Media Plan", "WHO / AAP", 2019)

make_unit("cyber", "13-15", "الخصوصية الرقمية للمراهق", "وقائي", "خفيف",
    "تقرير_سيبراني",
    "NIST, 'Digital Identity Guidelines', 2022; Common Sense Media, 'Teens and Privacy', 2021.",
    "Teens often overshare personal information online. Digital literacy includes privacy settings, strong passwords, and understanding data permanence.",
    "علّمي ابنك/ابنتك: لا تشارك عنوان منزلك أو رقم هاتفك علنًا. استخدم كلمة مرور قوية ومختلفة لكل حساب. صورة اليوم قد تبقى للأبد على الإنترنت — فكّر قبل أن تنشر. إعدادات الخصوصية ليست 'تعقيدًا' بل حماية.",
    ["خصوصية", "بيانات", "أمان_رقمي", "مراهقة"], "Digital Identity Guidelines", "NIST", 2022)

make_unit("cyber", "16-18", "الاحتيال والابتزاز الإلكتروني", "إرشادي", "شديد",
    "تقرير_سيبراني",
    "FBI IC3, 'Internet Crime Report', 2024.",
    "Sextortion and online scams targeting teens are rising; offenders often pose as peers to gain trust before exploiting victims.",
    "إذا تعرض ابنك/ابنتك لابتزاز إلكتروني أو احتيال: لا تلوميه — الجاني هو المسؤول. لا تدفعي أي مبلغ. احتفظي بكل الأدلة (رسائل، صور). بلّغي الشرطة فورًا. طمئنيه: 'سنواجه هذا معًا ولن تتضرر سمعتك.' هذا وقت الحماية لا العقاب.",
    ["ابتزاز", "احتيال", "أمان", "طارئ"], "Internet Crime Report", "FBI IC3", 2024)

make_unit("cyber", "16-18", "الذكاء الاصطناعي وأخلاقياته للشباب", "وقائي", "خفيف",
    "تقرير_سيبراني",
    "UNESCO, 'AI and Education: Guidance for Policy-Makers', 2021.",
    "AI tools like ChatGPT raise questions about academic integrity, critical thinking, and ethical use.",
    "ابنك/ابنتك يستخدم ChatGPT للواجبات؟ لا تمنعي بل علّمي: الذكاء الاصطناعي مساعد وليس بديلًا عن عقلك. استخدمه للبحث عن أفكار لا لنسخ الإجابات. افحص صحة المعلومات بنفسك. الهدف: أن تتعلم كيف تفكر، لا أن يكتب غيرك عنك.",
    ["ذكاء_اصطناعي", "أخلاقيات", "تعليم"], "AI and Education", "UNESCO", 2021)

print(f"\nTotal units: {sum(COUNTER.values()) - 4}")
print("DONE")
