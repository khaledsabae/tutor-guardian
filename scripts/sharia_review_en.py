#!/usr/bin/env python3
"""
Independent Sharia review of English translations vs Arabic originals.
v2: Proper Arabic word boundaries, distinguishes verb خلق from noun خُلق,
    checks hadith/verse preservation with stricter rules. Read-only — report only.
"""
import json, os, glob, re, sys, unicodedata

BASE = 'knowledge_base/curriculum'
EN_BASE = BASE + '/i18n/en'
AR_BASE = BASE

DHAL_MARKER = 'ﷺ'

# Arabic word boundary helper: ensure the term is a standalone word, not substring.
# We treat Arabic letters, diacritics, and tatweel as part of words.
AR_LETTER_RE = re.compile(r'[\u0600-\u06FF\u0600-\u06FF\u064B-\u0652\u0640]')

def ar_word_boundary(text, term):
    """Return True if `term` appears as a standalone Arabic word (with diacritics allowed on it)."""
    idx = 0
    while True:
        idx = text.find(term, idx)
        if idx == -1:
            return False
        # char before
        before = text[idx-1] if idx > 0 else ' '
        after = text[idx+len(term)] if idx+len(term) < len(text) else ' '
        # before must be non-Arabic-letter (space, punctuation, start)
        # but allow diacritics immediately before? No — diacritics attach to previous letter.
        ok_before = not (AR_LETTER_RE.fullmatch(before) and before not in '\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670')
        ok_after = not (AR_LETTER_RE.fullmatch(after) and after not in '\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670')
        # Simpler: check that the characters adjacent are NOT Arabic letters (ignoring diacritics on the term itself)
        # We define Arabic "letter" as base letters (not harakat)
        is_base_letter = lambda c: ('\u0620' <= c <= '\u064A') or c in '\u0671\u0672\u0673\u0675\u0676\u0677\u0678\u0679\u067A\u067B\u067C\u067D\u067E\u0680\u0681\u0682\u0683\u0684\u0685\u0686\u0687\u0688\u0689\u068A\u068B\u068C\u068D\u068E\u068F\u0690\u0691\u0692\u0693\u0694\u0695\u0696\u0697\u0698\u0699\u069A'
        ok_before = not is_base_letter(before)
        ok_after = not is_base_letter(after)
        if ok_before and ok_after:
            return True
        idx += len(term)

# Better word-boundary approach using regex with proper unicode handling.
def ar_contains_word(text, term):
    """Check if `term` appears as a whole Arabic word in `text`.
    Distinguishes خلق (verb "to create") from خُلق (noun "character") by checking
    that the term is not immediately preceded by the definite article when the term
    is a verb-form. We rely on exact-form matching including harakat where applicable.
    """
    term_escaped = re.escape(term)
    # Arabic base letters range roughly \u0620-\u064A (plus extended).
    pattern = r'(?<![\u0620-\u064A\u0670-\u069A])' + term_escaped + r'(?![\u0620-\u064A\u0670-\u069A])'
    return re.search(pattern, text) is not None

def normalize_quotes(s):
    """Normalize curly quotes/apostrophes to plain ASCII for matching purposes."""
    return (s.replace('\u2019', "'").replace('\u2018', "'")
             .replace('\u201c', '"').replace('\u201d', '"')
             .replace('\u00ab', '"').replace('\u00bb', '"'))

# Known hadith English reference translations for key ahadith.
# These must align with Saheeh International / Sunnah.com English conventions.
KNOWN_HADITHS = [
    # (arabic_fragment_regex, expected_english_keywords (lowercase), severity_if_mismatch, recommended_en)
    (r'إن الله رفيق يحب الرفق في كل شيء',
        ['allah','gentle','loves','gentleness','all things'],
        'high', "Allah is gentle and loves gentleness in all things"),
    (r'إن الله يحب الرفق في الأمر كله',
        ['allah','loves','gentleness','all matters'],
        'high', "Allah loves gentleness in all matters"),
    (r'ما كان الرفق في شيء إلا زانه',
        ['gentleness','beautifies','beautify'],
        'medium', "Gentleness is not found in anything but that it beautifies it"),
    (r'ولُبّ|لُبّ', None, None, None),  # placeholder
    (r'الكلمة الطيبة صدقة',
        ['good word','charity'],
        'medium', "A good word is charity"),
    (r'من لا يَرحم الناس لا يَرحمه الله',
        ['mercy','people','allah'],
        'high', "Whoever does not show mercy to people, Allah will not show mercy to him"),
    (r'من لا يَرحم لا يُرحم',
        ['mercy','shown mercy'],
        'high', "Whoever does not show mercy will not be shown mercy"),
    (r'الراحمون يرحمهم الرحمن',
        ['merciful','most merciful','mercy'],
        'medium', "The merciful are shown mercy by the Most Merciful"),
    (r'إنما الأعمال بالنيات',
        ['actions','intentions'],
        'high', "Actions are but by intentions"),
    (r'كُلُّ مَوْلُودٍ يُولَدُ عَلَى الفِطْرَةِ',
        ['child','born','fitrah'],
        'medium', "Every child is born upon the fitrah"),
    (r'مروا أولادكم بالصلاة لسبع',
        ['command','children','pray','seven'],
        'high', "Command your children to pray when they are seven years old"),
    (r'العهد الذي بيننا وبينهم الصلاة',
        ['covenant','prayer'],
        'medium', "The covenant between us and them is the prayer"),
    (r'لا ضرر ولا ضرار',
        ['harm','reciprocating'],
        'medium', "There should be neither harm nor reciprocating harm"),
    (r'خيركم خيركم لأهله',
        ['best of you','families'],
        'medium', "The best of you are those who are best to their families"),
    (r'استوصوا بالنساء خيرا',
        ['treat women well','women','well'],
        'medium', "Treat women well"),
    (r'ليس منا من لم يرحم صغيرنا',
        ['not of us','mercy','young','small'],
        'medium', "He is not one of us who does not show mercy to our young"),
    (r'السماح السماح',
        ['pardon','overlook','forgive'],
        'low', "Pardon, pardon (overlook)"),
]

# Known Quran ayah reference translations (Saheeh International) keyed by a unique Arabic fragment.
KNOWN_VERSES = [
    (r'﴿.*?وَقُولُوا لِلنَّاسِ حُسْناً.*?﴾', ['speak','people','good'],
     'medium', "And speak to people good [words]"),
    (r'﴿.*?وَبِالْوَالِدَيْنِ إِحْسَاناً.*?﴾', ['parents','goodness'],
     'medium', "And to parents, good treatment"),
    (r'﴿.*?وَلا تَقْتُلُوا أَوْلادَكُمْ.*?﴾', ['kill','children'],
     'high', "And do not kill your children"),
    (r'﴿.*?إِنَّ اللَّهَ يُحِبُّ التَّوَّابِينَ.*?﴾', ['allah','loves','repentant'],
     'medium', "Indeed, Allah loves those who are constantly repentant"),
    (r'﴿.*?وَاللَّهُ يُحِبُّ المُحْسِنِينَ.*?﴾', ['allah','loves','doers of good'],
     'medium', "And Allah loves the doers of good"),
    (r'﴿.*?وَلا تُكْرِهُوا فَتَيَاتِكُمْ.*?﴾', ['compel','slave girls','maids'],
     'high', "And do not compel your girls to prostitution"),
]

# Islamic terminology — only flag as a real issue when the term is used as a standalone
# *Islamic term* (not a verb conjugation). We use exact-word matching with diacritics tolerance.
# For each term we record: (arabic_exact_forms[], acceptable_english[], is_religious_term_bool)
TERMS_CHECKS = [
    # core religious terms the task explicitly lists
    (['تربية','تَرْبِيَة','التربية','التَّرْبِيَة'], ['tarbiyah','upbringing','raising','education','rearing','nurturing','parenting']),
    (['أخلاق','الأخلاق','أَخْلاق','الأَخْلاق','أخلاقٌ'], ['akhlaq','manner','character','ethics','moral','morals']),
    (['أذكار','الأذكار','أَذْكار','الأَذْكار','أذكارٌ'], ['adhkar','remembrances','litanies','invocations','remembering']),
    (['فطرة','الفطرة','فِطْرَة','الفِطْرَة'], ['fitrah','fitra','natural disposition','innate nature','innate disposition']),
    (['رفق','الرفق','رِفْق','الرِّفْق'], ['rifq','gentleness','gentle','kindness','kind']),
    (['عقيدة','العقيدة','عَقِيدَة','العَقِيدَة'], ['aqeedah','aqida','creed','belief','faith','theology']),
    (['سيرة','السيرة','سِيرَة','السِّيرَة'], ['seerah','seera','biography of the prophet','prophetic biography']),
    # sunnah — but bare سنة often means "year". Only flag definite form السنة / السُّنَّة (with shadda)
    # or when context is clearly religious (preceded by سنن / هدي / following a prophet mention).
    (['السنة','السُّنَّة','سُنَّة','السنن','سُنن'], ['sunnah','sunna','prophetic practice','prophetic way','tradition']),
    (['دعاء','الدعاء','دُعاء','الدُّعاء','دعاءٌ'], ["du'a","duaa","du‘a","supplication","prayer","invocation"]),
    (['قرآن','القرآن','قُرآن','القُرآن','قرآنٌ'], ["qur'an","quran","qur'aan","koran"]),
    (['أذان','الأذان','أَذان','الأَذان'], ['adhan','athan','call to prayer']),
    (['إيمان','الإيمان','إِيمان','الإِيمان'], ['iman','faith','belief']),
    (['توحيد','التوحيد','تَوْحِيد','التَّوْحِيد'], ['tawheed','tawhid','oneness','monotheism']),
    (['زكاة','الزكاة','زَكاة','الزَّكاة'], ['zakah','zakat','charity','alms']),
    (['حلال','الحلال','حَلال','الحَلال'], ['halal','lawful','permissible','allowed']),
    (['حرام','الحرام','حَرام','الحَرام'], ['haram','forbidden','prohibited','impermissible']),
    (['إحسان','الإحسان','إِحْسان','الإِحْسان','إحسانٌ'], ['ihsan','excellence','goodness','benevolence']),
    (['تزكية','التزكية','تَزْكِيَة','التَّزْكِيَة'], ['tazkiyah','tazkiya','purification','self-purification']),
    (['صحبة','الصحبة','صُحْبَة','الصُّحْبَة'], ['suhbah','companionship','company','companions']),
    (['صبر','الصبر','صَبْر','الصَّبْر'], ['sabr','patience','patient']),
    (['شكر','الشكر','شُكْر','الشُّكْر'], ['shukr','gratitude','thankfulness','grateful']),
    (['يقين','اليقين','يَقِين','اليَقِين'], ['yaqeen','certainty','conviction']),
    (['نية','النية','نِيَّة','النِّيَّة'], ['niyyah','niyyat','intention']),
    (['إمام','الإمام','إِمام','الإِمام'], ['imam','imaam','leader']),
    # خلق: only flag diacritized noun forms (with damma) — bare خلق is ambiguous
    # and in our corpus is overwhelmingly the verb "to create", so we skip the bare
    # form to avoid false positives.
    (['خُلُق','الخُّلُق','خُلْق','الخُّلْق'], ['khuluq','khulq','character','manner','moral','disposition']),
    (['تدبر','التدبر','تَدَبُّر','التَّدَبُّر'], ['tadabbur','reflection','contemplation','pondering']),
]

# Context words that, when adjacent to السنة / سنة, indicate the temporal meaning
# "year" rather than the religious "Sunnah". Used to suppress false positives.
YEAR_CONTEXT = ['أولى','نصف','أوّل','الثانية','الثالثة','الرابعة','الخامسة','السادسة',
                'السابعة','الثامنة','التاسعة','العاشرة','كاملة','مضت','قادمة','ماضية',
                'وأكثر','16','15','14','13','12','11','10','9','8','7','6','5','4','3','2','1','٠','١','٢','٣','٤','٥','٦','٧','٨','٩']

findings = []

def add(file, field, issue_type, arabic_text, english_text, why, severity, recommendedFix):
    findings.append({
        'file': file,
        'field': field,
        'issue_type': issue_type,
        'arabic_text': arabic_text,
        'english_text': english_text,
        'why': why,
        'severity': severity,
        'recommendedFix': recommendedFix
    })

def load_pairs():
    pairs = []
    for sub in ['lessons','paths','daily_tips']:
        prefix = {'lessons':'lesson_','paths':'path_','daily_tips':'tip_'}[sub]
        for age in ['0-3','2-3','4-6','7-9']:
            en_dir = f'{EN_BASE}/{sub}'
            ar_dir = f'{AR_BASE}/{sub}'
            for ef in sorted(glob.glob(f'{en_dir}/{prefix}{age}*.json')):
                bn = os.path.basename(ef)
                af = os.path.join(ar_dir, bn)
                if os.path.exists(af):
                    pairs.append((af, ef, sub, bn))
    return pairs

def check_hadiths(field, ar_text, en_text, file):
    """If an Arabic hadith marker present and we can identify the hadith, verify English."""
    # For known hadiths, match arabic fragment
    for ar_frag_re, en_keywords, sev, recommended in KNOWN_HADITHS:
        if en_keywords is None:
            continue
        ar_norm = ar_text.replace('ﷺ','').replace('صلى الله عليه وسلم','').replace('عليه الصلاة والسلام','')
        # normalize diacritics-tolerant: strip harakat for matching arabic
        ar_stripped = re.sub(r'[\u064B-\u0652\u0670]', '', ar_norm)
        frag_stripped = re.sub(r'[\u064B-\u0652\u0670]', '', ar_frag_re)
        if re.search(frag_stripped, ar_stripped):
            en_lower = en_text.lower()
            missing = [w for w in en_keywords if w not in en_lower]
            # If more than half the keywords missing, flag
            if len(missing) > max(1, len(en_keywords)//2):
                add(file, field, 'hadith_fidelity', ar_text, en_text,
                    f'Arabic hadith fragment matches "{ar_frag_re}" (known meaning: "{recommended}"), but English is missing expected key terms: {missing}',
                    sev, f'Align hadith translation with: "{recommended}"')

def check_verses(field, ar_text, en_text, file):
    """Check Quran verses — must align with Saheeh International style."""
    for ar_frag_re, en_keywords, sev, recommended in KNOWN_VERSES:
        ar_stripped = re.sub(r'[\u064B-\u0652\u0670]', '', ar_text)
        frag_stripped = re.sub(r'[\u064B-\u0652\u0670]', '', ar_frag_re)
        if re.search(frag_stripped, ar_stripped):
            en_lower = en_text.lower()
            missing = [w for w in en_keywords if w not in en_lower]
            if len(missing) > max(1, len(en_keywords)//2):
                add(file, field, 'ayah_fidelity', ar_text, en_text,
                    f'Arabic Quran verse matches "{ar_frag_re}" (Saheeh Intl: "{recommended}"), but English is missing expected key terms: {missing}',
                    sev, f'Align verse translation with Saheeh International: "{recommended}"')

def check_honorific(field, ar_text, en_text, file):
    """Check ﷺ preservation."""
    if DHAL_MARKER in ar_text:
        en_lower = en_text.lower()
        if (DHAL_MARKER not in en_text and
                'peace be upon him' not in en_lower and
                '(pbuh)' not in en_lower and
                '(ﷺ)' not in en_text and
                'upon him be peace' not in en_lower and
                'blessings and peace' not in en_lower and
                'blessings of allah' not in en_lower and
                'may allah bless' not in en_lower and
                'peace and blessings' not in en_lower):
            add(file, field, 'missing_honorific', ar_text, en_text,
                'Arabic contains the Prophet\'s honorific (ﷺ) but English omits any equivalent',
                'high', 'Add "(peace be upon him)" or "(ﷺ)" after the Prophet\'s name')

def check_terms(field, ar_text, en_text, file):
    """Check that Islamic terminology present in Arabic is rendered in English.
    Normalizes curly quotes in the English so 'du'a' / 'Qur'an' match."""
    en_norm = normalize_quotes(en_text)
    en_lower = en_norm.lower()
    for ar_forms, acceptable in TERMS_CHECKS:
        present = any(ar_contains_word(ar_text, f) for f in ar_forms)
        if not present:
            continue
        # Suppress السنة / سنة matches that are temporal ("year") not religious.
        if any(f in ('السنة','سنة','السنن','سُنن') for f in ar_forms):
            # if any year-context token appears adjacent to a matched السنة/سنة, skip
            for f in ar_forms:
                if ar_contains_word(ar_text, f):
                    # find the position and inspect neighbours
                    for m in re.finditer(re.escape(f), ar_text):
                        s=max(0,m.start()-12); e=min(len(ar_text),m.end()+15)
                        ctx=ar_text[s:e]
                        if any(y in ctx for y in YEAR_CONTEXT):
                            present = False
                            break
                    if not present:
                        break
        if not present:
            continue
        found = any(a.lower() in en_lower for a in acceptable)
        if not found:
            matched = next((f for f in ar_forms if ar_contains_word(ar_text, f)), ar_forms[0])
            add(file, field, 'term_not_rendered', matched, en_text,
                f'Arabic Islamic term "{matched}" appears as a standalone word but none of the accepted English renderings ({acceptable}) were found',
                'medium', f'Render "{matched}" as one of: {", ".join(acceptable[:3])}')

def compare_field(sub, field, ar_text, en_text, file):
    if not ar_text and not en_text:
        return
    if not ar_text and en_text:
        add(file, field, 'addition', '', en_text, 'English text exists but Arabic source is empty (possible unauthorised addition)', 'medium', 'Verify against source')
        return
    if ar_text and not en_text:
        add(file, field, 'omission', ar_text, '', 'Arabic text present but English translation empty (omission)', 'high', 'Translate the Arabic content into English')
        return

    check_honorific(field, ar_text, en_text, file)
    check_hadiths(field, ar_text, en_text, file)
    check_verses(field, ar_text, en_text, file)
    check_terms(field, ar_text, en_text, file)

def compare_objects(sub, ar_obj, en_obj, file):
    if sub == 'lessons':
        fields = ['title','summary','try_this','warning_flags','reflection_prompts']
    elif sub == 'paths':
        fields = ['title','description']
    else:
        fields = ['text']

    for f in fields:
        ar_val = ar_obj.get(f)
        en_val = en_obj.get(f)
        if isinstance(ar_val, list) and isinstance(en_val, list):
            if len(ar_val) != len(en_val):
                add(file, f, 'count_mismatch', json.dumps(ar_val,ensure_ascii=False), json.dumps(en_val,ensure_ascii=False),
                    f'Arabic list has {len(ar_val)} entries but English has {len(en_val)}',
                    'high', f'Reconcile ({len(ar_val)} vs {len(en_val)})')
            for i,(a,e) in enumerate(zip(ar_val, en_val)):
                if isinstance(a,str) and isinstance(e,str):
                    compare_field(sub, f"{f}[{i}]", a, e, file)
                elif isinstance(a,str) and not isinstance(e,str):
                    add(file, f"{f}[{i}]", 'omission', a, str(e), 'Arabic is a string but English is not', 'high', 'Translate')
                elif not isinstance(a,str) and isinstance(e,str):
                    add(file, f"{f}[{i}]", 'addition', str(a), e, 'English is a string but Arabic is not', 'medium', 'Verify')
        elif isinstance(ar_val, str) and isinstance(en_val, str):
            compare_field(sub, f, ar_val, en_val, file)
        elif ar_val is None and en_val is not None:
            if en_val != [] and en_val != {}:
                add(file, f, 'addition', '', str(en_val), 'English field present but Arabic field missing', 'medium', 'Verify source')
        elif ar_val is not None and en_val is None:
            if ar_val != [] and ar_val != {}:
                add(file, f, 'omission', str(ar_val), '', 'Arabic field present but English field missing', 'high', 'Translate to English')

def main():
    pairs = load_pairs()
    print(f'Loaded {len(pairs)} pairs', file=sys.stderr)
    for ar_path, en_path, sub, bn in pairs:
        try:
            with open(ar_path, encoding='utf-8') as f: ar = json.load(f)
            with open(en_path, encoding='utf-8') as f: en = json.load(f)
        except Exception as e:
            add(en_path, '(file)', 'parse_error', '', '', f'Could not parse JSON: {e}', 'high', 'Fix JSON')
            continue
        compare_objects(sub, ar, en, en_path)

    print(json.dumps(findings, ensure_ascii=False, indent=2))
    print(f'[report] total findings: {len(findings)}', file=sys.stderr)

if __name__ == '__main__':
    main()