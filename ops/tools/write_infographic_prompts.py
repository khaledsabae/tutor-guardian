#!/usr/bin/env python3
"""
كتابة بلوكات برومبت الإنفوجراف للدروس التي لا تملك واحدًا
=========================================================

    python3 ops/tools/write_infographic_prompts.py --dry-run
    python3 ops/tools/write_infographic_prompts.py --write --workers 4

٩٤ درسًا من ١٧٤ لا بلوك لها في `scripts/infographic_prompts.md`، فلا يُولَّد لها
إنفوجراف — لا عربي ولا إنجليزي — ويمرّ ذلك صامتًا لأن `buildable_targets()`
تعدّها «بلا برومبت» وتمضي.

لماذا نموذج لا قالب
-------------------
البلوك ليس بيانات وصفية: هو **تصميم** — عنوان يُقرأ في ثانية، و٣–٥ أقسام كل
واحد منها لوحة قائمة بذاتها. قالب يقلب `summary` إلى «القسم ١» ينتج ١٧٤ صورة
بنفس الهيكل ولا تخدم أيًّا من الدروس. النموذج يقرأ الدرس ويقرّر ما الذي يستحق
لوحة.

نُسخة من الموجود تُمرَّر كأمثلة، فيتعلّم الشكل من البلوكات الثمانين المكتوبة
بالفعل لا من وصفٍ لها.

⚠️ القيود المطبَّقة برمجيًّا لا بالرجاء
--------------------------------------
* ٣–٥ أقسام. أقلّ = صورة فارغة، أكثر = فوضى بصرية في 16:9.
* لا اقتباس لآية ولا حديث داخل بلوك: الإنفوجراف نصّ متحوّل إلى بكسل، ولا يمرّ
  على `check_quran_citations` ولا `check_hadith_citations` — فما يُرسم لا
  يستطيع أي حارس مطابقته بالمصحف. الأقسام تصف **موضوعًا** لا تقتبس نصًّا
  مقدَّسًا. أي بلوك يخالف يُرفض هنا، ولا يُكتب.
* المخرَج عربي: الملف مصدر للّغتين، و`--language` هو ما يقرّر لغة الصورة.
"""

import argparse
import importlib.util
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_MD = ROOT / "scripts" / "infographic_prompts.md"
LESSONS = ROOT / "knowledge_base" / "curriculum" / "lessons"

_spec = importlib.util.spec_from_file_location(
    "translate_curriculum", ROOT / "ops" / "tools" / "translate_curriculum.py")
tc = importlib.util.module_from_spec(_spec)
_argv, sys.argv = sys.argv, [sys.argv[0]]
try:
    _spec.loader.exec_module(tc)
finally:
    sys.argv = _argv

sys.path.insert(0, str(ROOT))
from scripts.infographic_prompts_lib import buildable_targets, parse_prompt_blocks  # noqa: E402

# نصّ مقدَّس داخل بلوك = صورة لا يستطيع أي حارس مطابقتها.
SACRED = re.compile(r"﴿|﴾|قال تعالى|قوله تعالى|قال النبي|قال رسول|ﷺ|رواه|أخرجه")

# 🚨 الكلمات المفتاحية وحدها لا تكفي، وهذا مُتحقَّق لا مفترض.
# أنتج النموذج قسمًا نصّه: «رسم يدٍ تكتب على ورقة "ليس المؤمن بالفاحش"» — حديث
# مقتبس **بلا ﷺ وبلا تخريج وبلا "قال النبي"**، فلم تلتقطه أي علامة أعلاه ومرّ.
# وهي بعينها الحالة التي يحذّر منها translate_curriculum.py («خيركم خيركم
# لأهله»): الاقتباس بلا إسناد هو أخطر الحالات لأنه لا يوجد ما يُقابَل به.
#
# فالإشارة الثانية مطابقة **بالهيكل الصامت** على فهرس الصحيحين — نفس آلية
# check_hadith_citations.py. تمسك «ليس المؤمن بالفاحش» ولا تمسك جملة جاهزة
# للأهل مثل «نقول يا سلام» لأنها ليست في الفهرس.
_hspec = importlib.util.spec_from_file_location(
    "check_hadith_citations", ROOT / "ops" / "tools" / "check_hadith_citations.py")
_h = importlib.util.module_from_spec(_hspec)
_argv2, sys.argv = sys.argv, [sys.argv[0]]
try:
    _hspec.loader.exec_module(_h)
finally:
    sys.argv = _argv2

_HADITH_SKELS = None
QUOTED = re.compile(r"[«\"“”'']\s*([؀-ۿ][^«»\"“”'']{6,})\s*[»\"“”'']")


def _hadith_skeletons() -> set:
    """هياكل صامتة لكل متن في الصحيحين — للمطابقة فقط لا للعرض.

    بنية الفهرس: {"source":…, "note":…, "books": {"البخاري": {رقم: هيكل}}}.
    والقيم **مخزَّنة كهياكل صامتة أصلًا**، فلا تُمرَّر على skeleton() ثانية.
    (المرور على المستوى الأعلى مباشرةً يعطي ٣ مفاتيح لا ١٤٬٩٤٠ رواية — وهو ما
    جعل البوابة تبدو عاملة وهي تقارن بلا شيء.)
    """
    global _HADITH_SKELS
    if _HADITH_SKELS is None:
        skels = set()
        for entries in _h._load_index().get("books", {}).values():
            for text in (entries.values() if isinstance(entries, dict) else entries):
                if isinstance(text, str) and text.strip():
                    skels.add(text.strip())
        _HADITH_SKELS = skels
    return _HADITH_SKELS


# سياقٌ دينيّ حول اقتباس = نصّ شرعي يُرسَم، أيًّا كان مصدره.
# ألفاظ تدلّ على **نقل عن مصدر**، لا مجرّد ذكرٍ للدين.
#
# القائمة الأولى ضمّت «الله» و«القرآن» و«دعاء» و«المؤمن»، فأشعلت ٤٠ بلوكًا من
# ١٦٠ — كلها سليمة: عناوين مثل «حفظ القرآن للطفل: منهج متدرج» أو جملة يتعلّمها
# الطفل مثل «الله ربي وخالقي». وحارسٌ يرفض ربع الصالح يُعطَّل، وتعطيلُه يعيد
# ما وُضع لأجله. المطلوب: نقلٌ عن حديث أو آية، لا حديثٌ عن الدين.
FAITH_CONTEXT = re.compile(
    r"لفتة إيمانية|حديث|الحديث|آية|الآية|قال تعالى|قوله تعالى|"
    r"قال النبي|قال رسول|عن النبي|رواه|أخرجه")


def needs_eye(blob: str) -> str | None:
    """اقتباس عربي في سطر يذكر مصدرًا شرعيًّا — **للمراجعة لا للرفض**.

    لماذا لا يُرفض: بتوسيع هذه الإشارة أُشعِل ١٩ بلوكًا سليمًا من ١٦٠ — «اللهم
    صلِّ على محمد» و«الله أكبر» و«اللهم اجعله بارًّا بوالديه». هذه أدعية ومتون
    مؤلَّفة، ورسمها في إنفوجرافيك تربوي أمر عادي تمامًا. وحارسٌ يرفض ما هو سليم
    يُعطَّل، وتعطيلُه يعيد ما وُضع لأجله.

    والتمييز بين «اللهم صلِّ على محمد» و«ليس المؤمن بالفاحش» ليس تمييزًا نصّيًّا:
    الأول دعاء والثاني إعادة صياغة لمتن حديث. لا يفرّق بينهما أي تعبير نمطي —
    يفرّق بينهما من يعرف المتون. فهذه قائمةُ عرضٍ على بشر، لا بوابة.
    """
    for line in blob.split("\n"):
        if line.lstrip().startswith("**Title:**"):
            continue
        if FAITH_CONTEXT.search(line):
            hit = QUOTED.search(line)
            if hit:
                return hit.group(1)
    return None


def quotes_hadith(blob: str) -> str | None:
    """يرجّع المقتبس إن كان نصًّا شرعيًّا يُراد رسمه، وإلا None.

    إشارتان، والاتحاد لا التقاطع — لأن كلًّا منهما تفوته حالة تمسكها الأخرى:

    ١) مطابقة الهيكل الصامت على الصحيحين: تمسك المتن الحرفي.
    ٢) اقتباس عربي داخل سياق دينيّ: تمسك ما تفوته الأولى.

    والثانية ضرورية لأن الأولى **لا تستطيع** مسك ما أنتجه النموذج فعلًا:
    «ليس المؤمن بالفاحش» **إعادة صياغة** لا لفظًا حرفيًّا («ليس المؤمن بالطعان
    ولا اللعان ولا الفاحش ولا البذيء»)، وهو في الترمذي لا في الصحيحين — والفهرس
    مقصور عليهما عمدًا. فالمطابقة النصّية تعجز مرتين: عن الصياغة وعن المصدر.

    ⚠️ وحدّها المتبقّي: اقتباسٌ شرعيّ بلا أي لفظ دينيّ حوله يمرّ. المكسب أن
    الرسم داخل صورة **لا يقابله حارس**، فالبلوك يصف الموضوع ولا يقتبس أصلًا.
    """
    skels = _hadith_skeletons()
    for quoted in QUOTED.findall(blob):
        sk = _h.skeleton(quoted)
        # ٢٥ حرفًا لا ١٢. الهيكل القصير ليس مميِّزًا: «اللهم صلِّ على محمد» يقع
        # داخل متون كثيرة فطابَق الفهرس، وهو صلاة يتعلّمها الطفل لا متنٌ يُنسب.
        # عتبة ١٢ حرفًا (~٤ كلمات) تمسك الشائع؛ ٢٥ (~٧ كلمات) تمسك المتن.
        if len(sk) >= 25 and any(sk in full for full in skels):
            return quoted
    return None

SYSTEM = """تكتب مواصفة إنفوجرافيك تربوي عربي واحد، لأبٍ أو أمّ يقرأ بسرعة.

المطلوب حقلان فقط:

**Title:** عنوان قصير جذّاب (٣–٨ كلمات). سؤال أو وعد عملي، لا عنوان أكاديمي.
**Sections:** ٣ إلى ٥ أقسام مرقّمة. كل قسم سطر واحد يصف **لوحة بصرية قائمة
بذاتها**: ما الذي يظهر فيها (مخطط، مقارنة، خطوات، تحذيرات) وما مضمونه.

القواعد:
1. الأقسام تصف ما يُرسَم لا ما يُقال. «مقارنة: ما يقوله الأب مقابل ما يسمعه
   الطفل» لوحة؛ «أهمية التواصل» ليست لوحة.
2. اجعل قسمًا واحدًا على الأقل عمليًّا مباشرًا (خطوات، جدول يومي، جُمل جاهزة).
3. واحدًا يمكن أن يكون تحذيرًا أو خطأً شائعًا — الأهل يتذكّرون ما يتجنّبونه.
4. 🚨 لا تقتبس آية ولا حديثًا ولا تكتب ﷺ. صف الموضوع فقط («لفتة إيمانية عن
   الرفق») — النص المرسوم داخل صورة لا يستطيع أي فحص مطابقته بالمصحف، فلا
   يُقتبس أصلًا.
5. عربي فصيح واضح، بلا إنجليزية.

أرجع JSON فقط: {"title": "...", "sections": ["...", "..."]}"""


def _fields(doc: dict) -> str:
    keep = ("title", "summary", "try_this", "reflection_prompts", "age_group", "domain")
    return json.dumps({k: doc[k] for k in keep if doc.get(k)}, ensure_ascii=False)


def draft(lesson_id: str) -> dict:
    path = LESSONS / f"{lesson_id}.json"
    if not path.exists():
        return {"id": lesson_id, "status": "failed", "reason": "لا ملف درس"}
    doc = json.loads(path.read_text(encoding="utf-8"))
    try:
        raw, _ = tc._post(tc.TRANSLATOR_MODEL, SYSTEM, _fields(doc))
        out = tc._parse_json(raw)
    except Exception as e:
        return {"id": lesson_id, "status": "failed", "reason": f"{type(e).__name__}: {e}"}

    title = str(out.get("title", "")).strip().strip('"')
    # The model numbers its own sections about half the time, and render() adds
    # numbering too — leaving "1. 1. مقارنة…". Strip any leading ordinal,
    # Arabic-Indic digits included, before rendering.
    sections = []
    for raw_s in (out.get("sections") or []):
        line = re.sub(r"^\s*[\d\u0660-\u0669]+\s*[.)\-–]\s*", "", str(raw_s).strip())
        if line:
            sections.append(line)

    if not title:
        return {"id": lesson_id, "status": "rejected", "reason": "بلا عنوان"}
    if not 3 <= len(sections) <= 5:
        return {"id": lesson_id, "status": "rejected",
                "reason": f"{len(sections)} أقسام (المطلوب ٣–٥)"}
    blob = title + " " + " ".join(sections)
    if SACRED.search(blob):
        return {"id": lesson_id, "status": "rejected",
                "reason": "يقتبس نصًّا شرعيًّا — لا يُرسم داخل صورة"}
    hit = quotes_hadith(blob)
    if hit:
        return {"id": lesson_id, "status": "rejected",
                "reason": f"يقتبس حديثًا بلا إسناد: «{hit[:40]}»"}
    if re.search(r"[A-Za-z]{4,}", blob):
        return {"id": lesson_id, "status": "rejected", "reason": "فيه إنجليزية"}

    return {"id": lesson_id, "status": "drafted", "title": title,
            "sections": sections, "age_group": doc.get("age_group", ""),
            "domain": doc.get("domain", ""),
            "review": needs_eye(title + "\n" + "\n".join(sections))}


def render(block: dict, number: int) -> str:
    lines = [f"#### {number}. `{block['id']}`",
             f"**Title:** \"{block['title']}\"",
             "**Sections:**"]
    lines += [f"{i}. {s}" for i, s in enumerate(block["sections"], 1)]
    return "\n".join(lines) + "\n\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if not args.write and not args.dry_run:
        ap.error("مرّر --dry-run أو --write")

    _ready, no_prompt = buildable_targets("en")
    # 🚨 القائمة تأتي من docs/lesson_index.json وفيه معرّفات قديمة قصيرة
    # (lesson_10-12_cyber_01) لدروس أُعيدت تسميتها من زمن — لا ملف منهج لها،
    # فالنموذج لا يجد ما يقرؤه. عشرة من الأربعة والتسعين كذلك. نستهدف ما له
    # ملف درس فعلًا، وإلا أنفقنا نداءات على أشباح.
    real = {p.stem for p in LESSONS.glob("*.json")}
    live = [t for t in no_prompt if t in real]
    dead = [t for t in no_prompt if t not in real]
    targets = live[:args.limit] if args.limit else live
    print(f"📝 {len(no_prompt)} بلا بلوك · {len(live)} درسًا حقيقيًّا "
          f"· {len(dead)} معرّفًا ميتًا في الفهرس (يُتجاهل)")
    print(f"   سنكتب {len(targets)}\n")
    if args.dry_run:
        for t in targets[:15]:
            print(f"  [dry-run] {t}")
        return

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(draft, targets))

    ok = [r for r in results if r["status"] == "drafted"]
    bad = [r for r in results if r["status"] != "drafted"]

    existing = parse_prompt_blocks()
    start = len(existing)
    text = PROMPTS_MD.read_text(encoding="utf-8").rstrip() + "\n\n"
    text += ("\n---\n\n## 📂 دروس أُضيفت لاحقًا — بلوكات مكتوبة آليًّا"
             " ومراجَعة بشريًّا قبل التوليد\n\n")
    for i, b in enumerate(sorted(ok, key=lambda r: r["id"]), start + 1):
        text += render(b, i)
    PROMPTS_MD.write_text(text, encoding="utf-8")

    print("═" * 60)
    print(f"  مكتوب  : {len(ok)}")
    print(f"  مرفوض  : {len(bad)}")
    for r in bad[:10]:
        print(f"     ✗ {r['id']}: {r['reason']}")
    after = parse_prompt_blocks()
    print(f"  بلوكات الملف: {start} → {len(after)}")
    print("═" * 60)

    eye = [r for r in ok if r.get("review")]
    if eye:
        print(f"\n👁  {len(eye)} بلوكًا يقتبس نصًّا في سياق شرعي — **للمراجعة "
              "البشرية لا للرفض**:")
        print("   (دعاء أو متن مؤلَّف = سليم · متن حديث أو آية = يُعاد صياغته وصفًا)")
        for r in eye[:20]:
            print(f"     {r['id']}: «{r['review'][:56]}»")


if __name__ == "__main__":
    main()
