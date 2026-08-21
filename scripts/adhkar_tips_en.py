"""English wording for the 124 `tip` items in the family adhkar pack.

Kept as a separate, reviewable table rather than generated at build time: these
are the sentences a parent reads on their lock screen, and they should be
diff-able like any other content.

Rules that shaped the wording:

* **Nothing here renders scripture in English.** Where a tip quotes an ayah or a
  hadith, the Arabic is carried through verbatim and the English says what it
  means, introduced as a meaning. `ops/tools/check_quran_rendering.py` exists for
  exactly this line and these entries have to stay on the right side of it.
* Imperative and short, because the delivery surface is a notification.
* "your child" rather than "him/her": the Arabic addresses a parent about a
  child whose gender the pack does not know.
"""

# id → (text, source, topic)
TIPS_EN: dict[str, tuple[str, str, str]] = {
    "t_001": (
        "Start your day by smiling at your children: a smile is charity, and a "
        "home takes its shape from the first moment of the morning.",
        "Parenting guidance — drawn from the hadith «تبسمك في وجه أخيك صدقة»",
        "Tip",
    ),
    "t_002": (
        "Before you criticise, put your hand on your child's head and lower your "
        "voice: «الرفق لا يكون في شيء إلا زانه» — gentleness adorns whatever it "
        "touches.",
        "Parenting guidance — drawn from the hadith on gentleness",
        "Tip",
    ),
    "t_003": (
        "Set aside ten minutes a day to listen to your child without "
        "interrupting — it tells them they are safe and respected.",
        "Parenting guidance",
        "Tip",
    ),
    "t_004": (
        "Do not compare your children to each other or to anyone else's; being "
        "fair between them starts with seeing each one as themselves.",
        "Parenting guidance",
        "Tip",
    ),
    "t_005": (
        "Teach your child one du'a this week and say it together: whoever takes "
        "a path in search of knowledge is walking a path to Paradise.",
        "Parenting guidance — drawn from the hadith on knowledge",
        "Tip",
    ),
    "t_006": (
        "Mark the smallest achievement with a kind word: praise that names the "
        "effort builds a confident child who loves doing good.",
        "Parenting guidance",
        "Tip",
    ),
    "t_007": (
        "When your child angers you, take a breath before you answer: «الصبر عند "
        "الصدمة الأولى» — patience counts at the first shock.",
        "Parenting guidance — drawn from the hadith on patience",
        "Tip",
    ),
    "t_008": (
        "Read your child the story of a prophet or a companion each night before "
        "sleep: hearts grow around the people they are shown.",
        "Parenting guidance",
        "Tip",
    ),
    "t_009": (
        "Do not let worship disappear from the house; praying in congregation "
        "with your children — even two rak'ahs — teaches more than a thousand "
        "lectures.",
        "Parenting guidance",
        "Tip",
    ),
    "t_010": (
        "Forgive yourself for your parenting mistakes and ask Allah to guide "
        "you: a parent is a shepherd, and a shepherd sometimes errs and then "
        "puts it right.",
        "Parenting guidance — drawn from the hadith of the shepherd",
        "Tip",
    ),
    "t_011": (
        "Replace “don't do that” with “what if we did this instead?” — pointing "
        "somewhere is what earns you a response.",
        "Parenting guidance",
        "Tip",
    ),
    "t_012": (
        "When your child does wrong, separate the child from the behaviour: you "
        "are dear to us, and this particular thing was wrong.",
        "Parenting guidance",
        "Tip",
    ),
    "t_013": (
        "Give your child a small corner of the house for reading and quiet — a "
        "visible invitation to settle.",
        "Parenting guidance",
        "Tip",
    ),
    "t_014": (
        "Accept your child's apology at once, and teach them to repair what they "
        "broke rather than simply be punished for it.",
        "Parenting guidance",
        "Tip",
    ),
    "t_015": (
        "When your child speaks, come down to their eye level and put down "
        "whatever is in your hands — there is no higher respect.",
        "Parenting guidance",
        "Tip",
    ),
    "t_016": (
        "Get your children used to saying “thank you” and “جزاك الله خيرًا” for "
        "any help around the house.",
        "Parenting guidance",
        "Tip",
    ),
    "t_017": (
        "Take your child to the mosque gently and cheerfully, and teach them "
        "stillness through love rather than fear.",
        "Parenting guidance",
        "Tip",
    ),
    "t_018": (
        "Make Friday feel different at home: good scent, and Surat al-Kahf read "
        "together.",
        "Parenting guidance",
        "Tip",
    ),
    "t_019": (
        "Bring your children into cooking or setting the table — working "
        "together is where responsibility grows.",
        "Parenting guidance",
        "Tip",
    ),
    "t_020": (
        "When you shop, teach your child the difference between a real need and "
        "a passing want.",
        "Parenting guidance",
        "Tip",
    ),
    "t_021": (
        "Keep a small jar at home called “the good jar”, where your child puts "
        "whatever they like for those in need.",
        "Parenting guidance",
        "Tip",
    ),
    "t_022": (
        "Do not shout at a crying child. Say instead: I am here with you, and "
        "when you are calm we will talk.",
        "Parenting guidance",
        "Tip",
    ),
    "t_023": (
        "Hug your children several times a day: being held is what safety feels "
        "like before a child has words for it.",
        "Parenting guidance",
        "Tip",
    ),
    "t_024": (
        "Listen to your child's small stories with real attention, so that they "
        "trust you with the large ones later.",
        "Parenting guidance",
        "Tip",
    ),
    "t_025": (
        "Promise your child nothing you cannot deliver: keeping your word is the "
        "ground their sense of safety stands on.",
        "Parenting guidance",
        "Tip",
    ),
    "t_026": (
        "Teach your child how to say “no” to a stranger, or to anything that "
        "makes them uncomfortable.",
        "Parenting guidance",
        "Tip",
    ),
    "t_027": (
        "Set screen and phone hours for the house, and be the first to keep to "
        "them.",
        "Parenting guidance",
        "Tip",
    ),
    "t_028": (
        "Keep the dinner table completely free of phones: mealtime is the "
        "family's talking time.",
        "Parenting guidance",
        "Tip",
    ),
    "t_029": (
        "Praise the attempt and the effort spent, not only the cleverness or the "
        "result: “I am proud of how hard you worked.”",
        "Parenting guidance",
        "Tip",
    ),
    "t_030": (
        "Teach your children to settle their small disagreements by talking and "
        "taking turns.",
        "Parenting guidance",
        "Tip",
    ),
    "t_031": (
        "When your child is angry, help them put the feeling into words: “I can "
        "see that this upset you.”",
        "Parenting guidance",
        "Tip",
    ),
    "t_032": (
        "Say the morning and evening adhkar out loud at home, so your children "
        "learn them simply by hearing them again and again.",
        "Parenting guidance",
        "Tip",
    ),
    "t_033": (
        "Hold a fifteen-minute family sitting each week on one simple point of "
        "faith or character.",
        "Parenting guidance",
        "Tip",
    ),
    "t_034": (
        "Encourage your children into a sport that serves them — swimming or "
        "running — so the body is built well.",
        "Parenting guidance",
        "Tip",
    ),
    "t_035": (
        "Do not discuss your child's faults in front of relatives or friends: "
        "their dignity is a trust you are holding.",
        "Parenting guidance",
        "Tip",
    ),
    "t_036": (
        "If you find out your child did wrong, take it up with them alone in the "
        "room — not in front of their brothers and sisters.",
        "Parenting guidance",
        "Tip",
    ),
    "t_037": (
        "Teach your child that asking permission before entering a room is an "
        "adab the Qur'an taught, and it protects everyone's privacy.",
        "Parenting guidance",
        "Tip",
    ),
    "t_038": (
        "Train your child to keep the household's business inside the house.",
        "Parenting guidance",
        "Tip",
    ),
    "t_039": (
        "Let your child choose their own clothes, within reason, so they learn to "
        "decide and to stand on their own.",
        "Parenting guidance",
        "Tip",
    ),
    "t_040": (
        "Teach your children never to mock anyone for their looks, their colour "
        "or their clothes: «إن الله لا ينظر إلى صوركم» — Allah does not look at "
        "your forms.",
        "Parenting guidance — drawn from the hadith «إن الله لا ينظر إلى صوركم»",
        "Tip",
    ),
    "t_041": (
        "Thank your wife in front of the children, and thank your husband in "
        "front of them: how the two of you treat each other is what they copy.",
        "Parenting guidance",
        "Tip",
    ),
    "t_042": (
        "When you travel or go out, bring the children into the planning and let "
        "them choose some of it.",
        "Parenting guidance",
        "Tip",
    ),
    "t_043": (
        "Put up a simple daily chart and let your child tick off a prayer or a "
        "piece of homework once it is done.",
        "Parenting guidance",
        "Tip",
    ),
    "t_044": (
        "Teach your child istighfar and the du'a of Yunus in distress: «لَا "
        "إِلَٰهَ إِلَّا أَنتَ سُبْحَانَكَ إِنِّي كُنتُ مِنَ الظَّالِمِينَ». Its "
        "meaning: there is no god but You, glory be to You, I have been among "
        "the wrongdoers.",
        "Parenting guidance — the wording is Qur'an, Surat al-Anbiya' 21:87",
        "Tip",
    ),
    "t_045": (
        "When you see your child helping anyone at all, thank them on the spot: "
        "“how beautiful your hands are when they help.”",
        "Parenting guidance",
        "Tip",
    ),
    "t_046": (
        "Teach your son that manhood is in gentleness and in protecting the weak "
        "— not in force or in shouting.",
        "Parenting guidance",
        "Tip",
    ),
    "t_047": (
        "Teach your daughter modesty, and pride in who she is and in the "
        "character her faith gives her.",
        "Parenting guidance",
        "Tip",
    ),
    "t_048": (
        "Explain the reason behind a rule simply, instead of handing down a bare "
        "order.",
        "Parenting guidance",
        "Tip",
    ),
    "t_049": (
        "Be patient with your child's endless questions: curiosity is the engine "
        "of every bit of learning they will do.",
        "Parenting guidance",
        "Tip",
    ),
    "t_050": (
        "If you do not know the answer to your child's question about faith or "
        "science, say so honestly: “good question — let's go and find out "
        "together.”",
        "Parenting guidance",
        "Tip",
    ),
    "t_051": (
        "Teach your child the du'a for entering and leaving the bathroom, so "
        "adab reaches even the smallest corner of their day.",
        "Parenting guidance",
        "Tip",
    ),
    "t_052": (
        "Teach your child the du'a for travelling, and to look for barakah in "
        "every journey.",
        "Parenting guidance",
        "Tip",
    ),
    "t_053": (
        "Keep a small library at home with illustrated stories of the prophets.",
        "Parenting guidance",
        "Tip",
    ),
    "t_054": (
        "Encourage your child to read by leaving a book beside their bed every "
        "night.",
        "Parenting guidance",
        "Tip",
    ),
    "t_055": (
        "At meals, get your child used to never criticising food: if they want "
        "it they eat it, and if not they leave it politely.",
        "Parenting guidance",
        "Tip",
    ),
    "t_056": (
        "Teach your child not to waste water in wudu or in the shower: looking "
        "after a blessing is how you thank Allah for it.",
        "Parenting guidance",
        "Tip",
    ),
    "t_057": (
        "Train your child to switch off lights and devices nobody is using — a "
        "small, daily sense of responsibility.",
        "Parenting guidance",
        "Tip",
    ),
    "t_058": (
        "When visiting relatives, teach your children a warm greeting, asking "
        "permission, and how to sit with people.",
        "Parenting guidance",
        "Tip",
    ),
    "t_059": (
        "If your child is afraid of something, never make light of the fear — "
        "hold them and make them feel safe.",
        "Parenting guidance",
        "Tip",
    ),
    "t_060": (
        "Teach your child to honour a trust: a toy borrowed from a friend goes "
        "back whole and clean.",
        "Parenting guidance",
        "Tip",
    ),
    "t_061": (
        "Get your children used to telling the truth and owning a mistake "
        "without fearing what follows.",
        "Parenting guidance",
        "Tip",
    ),
    "t_062": (
        "Make bedtime a warm moment: a hand on the head, the last two surahs, "
        "and a du'a for good.",
        "Parenting guidance",
        "Tip",
    ),
}

TIPS_EN.update({
    "t_063": (
        "If your child had a hard day at school, listen first and be the safe "
        "place they come back to.",
        "Parenting guidance",
        "Tip",
    ),
    "t_064": (
        "Teach your child that failing is not the end of the world — it is "
        "another go at learning something.",
        "Parenting guidance",
        "Tip",
    ),
    "t_065": (
        "Let your child try things and discover under your eye, without tying "
        "their hands entirely.",
        "Parenting guidance",
        "Tip",
    ),
    "t_066": (
        "Teach your children to respect the elderly and to help them carry what "
        "is heavy.",
        "Parenting guidance",
        "Tip",
    ),
    "t_067": (
        "Get your children used to kindness towards animals and never harming "
        "them: «في كل كبد رطبة أجر» — there is reward in every living creature.",
        "Parenting guidance — drawn from the hadith «في كل كبد رطبة أجر»",
        "Tip",
    ),
    "t_068": (
        "When your child plants something, remind them that everyone who "
        "benefits from it later is written for them.",
        "Parenting guidance",
        "Tip",
    ),
    "t_069": (
        "Teach your child to respect their teachers, to listen politely, and to "
        "remember what they owe them.",
        "Parenting guidance",
        "Tip",
    ),
    "t_070": (
        "Keep a small signal or a password between you and your children — a "
        "quick, private way to reach each other.",
        "Parenting guidance",
        "Tip",
    ),
    "t_071": (
        "Do not step into every detail of your children's play unless there is "
        "danger: let them negotiate it out.",
        "Parenting guidance",
        "Tip",
    ),
    "t_072": (
        "Teach your child that apologising is strength, not weakness, and that "
        "what makes it possible is humility.",
        "Parenting guidance",
        "Tip",
    ),
    "t_073": (
        "Let your home be one where Allah's name is said often — in tasbih, in "
        "praise, in du'a.",
        "Parenting guidance",
        "Tip",
    ),
    "t_074": (
        "Get your child used to keeping promises and appointments: a Muslim who "
        "promises, delivers.",
        "Parenting guidance",
        "Tip",
    ),
    "t_075": (
        "Teach your children to compete in doing good, without bitterness or "
        "envy.",
        "Parenting guidance",
        "Tip",
    ),
    "t_076": (
        "If you see a gift in your child — drawing, calligraphy, memorising "
        "Qur'an — feed it and cheer it on.",
        "Parenting guidance",
        "Tip",
    ),
    "t_077": (
        "Have your children make du'a for your parents, their grandparents, for "
        "mercy and health — that is how lasting birr is planted.",
        "Parenting guidance",
        "Tip",
    ),
    "t_078": (
        "Teach your child never to pry or to steal a look into what belongs to "
        "someone else.",
        "Parenting guidance",
        "Tip",
    ),
    "t_079": (
        "When there is trouble between your children, hear each one alone and "
        "without taking a side, before you judge.",
        "Parenting guidance",
        "Tip",
    ),
    "t_080": (
        "Teach your child that digital honesty is knowing Allah sees them on the "
        "internet and on the phone as everywhere else.",
        "Parenting guidance",
        "Tip",
    ),
    "t_081": (
        "Steer your child towards content that is useful and right for their "
        "age, so the hours are not simply spent.",
        "Parenting guidance",
        "Tip",
    ),
    "t_082": (
        "Explain to your child that games and phones are a small amusement, not "
        "the whole of life.",
        "Parenting guidance",
        "Tip",
    ),
    "t_083": (
        "Teach your children to visit their cousins on both sides — this is how "
        "the ties of kinship are kept strong.",
        "Parenting guidance",
        "Tip",
    ),
    "t_084": (
        "Let your children help choose and wrap the Eid gifts, and spread the "
        "joy with you.",
        "Parenting guidance",
        "Tip",
    ),
    "t_085": (
        "Teach your child salat al-istikhara for when they are torn between two "
        "good options.",
        "Parenting guidance",
        "Tip",
    ),
    "t_086": (
        "Get your children used to saying bismillah before drinking, thanking "
        "Allah after, and drinking in three breaths.",
        "Parenting guidance",
        "Tip",
    ),
    "t_087": (
        "Teach your child not to talk with food in their mouth — for their "
        "safety as much as for good manners.",
        "Parenting guidance",
        "Tip",
    ),
    "t_088": (
        "When your child looks sad, ask: “would you like me to listen, or would "
        "you like a hug?”",
        "Parenting guidance",
        "Tip",
    ),
    "t_089": (
        "Teach your child that a beautiful character leaves a deeper mark on "
        "people than expensive clothes ever do.",
        "Parenting guidance",
        "Tip",
    ),
    "t_090": (
        "Get your children used to the dhikr for leaving the house: «بِسْمِ "
        "اللَّهِ تَوَكَّلْتُ عَلَى اللَّهِ» — in the name of Allah, I place my "
        "trust in Allah.",
        "Parenting guidance",
        "Tip",
    ),
    "t_091": (
        "Teach your children to say bismillah and to praise Allah when they put "
        "on new clothes.",
        "Parenting guidance",
        "Tip",
    ),
    "t_092": (
        "Keep a box at home for recycling paper or saving leftover food — "
        "responsibility learned by doing.",
        "Parenting guidance",
        "Tip",
    ),
    "t_093": (
        "Teach your child to lay out their day between prayer, schoolwork, play "
        "and sleep.",
        "Parenting guidance",
        "Tip",
    ),
    "t_094": (
        "Thank your child when they do what you asked the first time: praise is "
        "what makes it happen again.",
        "Parenting guidance",
        "Tip",
    ),
    "t_095": (
        "If your child is struggling with a subject, help them through it in "
        "small encouraging steps and without tension.",
        "Parenting guidance",
        "Tip",
    ),
    "t_096": (
        "Teach your child that swallowing anger and forgiving a friend is "
        "something Allah raises them for.",
        "Parenting guidance",
        "Tip",
    ),
    "t_097": (
        "Get your children used to giving salam out loud when they come into the "
        "house.",
        "Parenting guidance",
        "Tip",
    ),
    "t_098": (
        "Teach your child that Allah sees in the dark as He sees in the light: "
        "knowing you are seen is where uprightness begins.",
        "Parenting guidance",
        "Tip",
    ),
    "t_099": (
        "Let your child feel that their home is the safest, most loving place in "
        "the world.",
        "Parenting guidance",
        "Tip",
    ),
    "t_100": (
        "Remember that du'a made for your children when they are not there works "
        "wonders: never tire of making it.",
        "Parenting guidance",
        "Tip",
    ),
    "t_101": (
        "Teach your child that hardship is an opening for patience and for "
        "drawing nearer to Allah — not anger from Him.",
        "Parenting guidance",
        "Tip",
    ),
    "t_102": (
        "Tell your child, again and again, that your love does not depend on "
        "their performance or their marks.",
        "Parenting guidance",
        "Tip",
    ),
    "t_103": (
        "Teach your child to make du'a for themselves, for their parents and for "
        "the Muslims after every prayer.",
        "Parenting guidance",
        "Tip",
    ),
    "t_104": (
        "Build good memories with your children in every season and every Eid.",
        "Parenting guidance",
        "Tip",
    ),
    "t_105": (
        "Be the support your child always turns to, so they never go looking for "
        "it among strangers.",
        "Parenting guidance",
        "Tip",
    ),
    "t_106": (
        "Teach your child to hold to their faith, their values and their "
        "character with confidence and love.",
        "Parenting guidance",
        "Tip",
    ),
    "t_107": (
        "Remember that your children read what you do and where you stand far "
        "more closely than they listen to your advice.",
        "Parenting guidance",
        "Tip",
    ),
    "t_108": (
        "And last: ask Allah every day for guidance, for tawfiq, and for barakah "
        "in your children.",
        "Parenting guidance",
        "Tip",
    ),
    "t_109": (
        "Give your child a moment to think before sleep, and ask: “what was the "
        "best thing that happened today, and what made you happy?”",
        "Parenting guidance",
        "Tip",
    ),
    "t_110": (
        "Teach your children to respect privacy and never to open someone else's "
        "messages or devices without asking.",
        "Parenting guidance",
        "Tip",
    ),
    "t_111": (
        "If your child is worked up or angry, give them a cushion or a squeeze "
        "toy to let the charge out safely.",
        "Parenting guidance",
        "Tip",
    ),
    "t_112": (
        "Teach your children to seek refuge in Allah from the shaytan when anger "
        "stirs.",
        "Parenting guidance",
        "Tip",
    ),
    "t_113": (
        "Keep a daily family hour with no screens or phones at all, so people "
        "actually talk to each other.",
        "Parenting guidance",
        "Tip",
    ),
    "t_114": (
        "If you promised your child a reward for finishing something, give it "
        "the moment they finish.",
        "Parenting guidance",
        "Tip",
    ),
    "t_115": (
        "Train your child to pack their own school bag and lay out their clothes "
        "each evening before bed.",
        "Parenting guidance",
        "Tip",
    ),
    "t_116": (
        "Teach your child the du'a for sleep: «بِاسْمِكَ اللَّهُمَّ أَمُوتُ "
        "وَأَحْيَا» — in Your name, O Allah, I die and I live — and reassure "
        "them that Allah is guarding them while they sleep.",
        "Parenting guidance",
        "Tip",
    ),
    "t_117": (
        "Keep a chart at home that rotates the small chores between the "
        "children — fairness and responsibility in one place.",
        "Parenting guidance",
        "Tip",
    ),
    "t_118": (
        "Thank your child warmly, and in front of everyone, when they go and "
        "help a friend or a neighbour.",
        "Parenting guidance",
        "Tip",
    ),
    "t_119": (
        "If your child mispronounces a word or an ayah, correct it calmly and "
        "kindly, and never laugh at them.",
        "Parenting guidance",
        "Tip",
    ),
    "t_120": (
        "Teach your child that truth always brings you out, and that lying cuts "
        "the rope of trust and safety.",
        "Parenting guidance",
        "Tip",
    ),
    "t_121": (
        "Train your children to switch the devices off and get ready for bed an "
        "hour early, so the mind can settle.",
        "Parenting guidance",
        "Tip",
    ),
    "t_122": (
        "If your child has a hard project or assignment, break it down with them "
        "into small, encouraging steps.",
        "Parenting guidance",
        "Tip",
    ),
    "t_123": (
        "Teach your child that their body is their own, and that nobody may "
        "touch them in a way that makes them uncomfortable.",
        "Parenting guidance",
        "Tip",
    ),
    "t_124": (
        "Before sleep, take your child's hand, read the bedtime adhkar together, "
        "and name the good things they did today.",
        "Parenting guidance",
        "Tip",
    ),
})

# The Arabic side, corrected in the same commit rather than smoothed over in
# translation. A fluent English rendering of a corrupt source hides the corruption
# — that lesson was paid for once already, on «سفينة» and «حق-half».
ARABIC_FIXES: dict[str, tuple[str, str]] = {
    # typo: المبتول → المبذول
    "t_029": ("الجهد المبتول", "الجهد المبذول"),
    # typo: doubled alif
    "t_042": ("وااختيار", "واختيار"),
    # typo: الضغيف → الضعيف
    "t_046": ("الضغيف", "الضعيف"),
    # garbled word; the sentence needs a verb that governs «بأن الله يحفظه»
    "t_116": ("والمحي بأن", "وطمْئِنه بأن"),
    # Egyptian dialect in a pack unified to plain MSA in 1.0.47
    "t_022": ("أنا معك وجمبك لما تهدأ نتكلم", "أنا معك وبجانبك، وحين تهدأ نتحدث"),
    "t_031": (
        "أنا شايف إنك زعلان عشان الشغلة دي",
        "أرى أنك حزين بسبب هذا الأمر",
    ),
    "t_045": ("ما أجمل يديك وهي بتساعد", "ما أجمل يديك وهي تساعد"),
}
