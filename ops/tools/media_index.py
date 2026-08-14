"""
تسجيل الميديا في docs/lesson_index.json — إدراج أو استبدال، لا إسناد
====================================================================

يُستورَد من المولّدات. ملف مولَّد لا يُسجَّل في الفهرس **لا يصل المستخدم**:
`/lesson-assets` يقرأ الفهرس لا القرص، فحلقة إنجليزية على القرص وغير مفهرسة
تعني أن المستخدم الإنجليزي يظلّ يسمع العربي — وهذا وقع فعلًا: ثلاث حلقات
إنجليزية على القرص و**صفر** في الفهرس، لأن المولّد ينزّل ولا يسجّل.

🚨 لماذا `upsert` لا إسناد
--------------------------
`scripts/regen_podcasts.py:116` يفعل هذا:

    by_id[lid]["assets"]["podcasts"] = [{...}]

أي **يستبدل القائمة كلها**. نسخُه في مولّد إنجليزي يمحو مرجع العربي عند أول
تنزيل ناجح. والملف يظل على القرص، فـ`check_served_assets.py` لا يرى شيئًا
(يفحص المُشار إليه → موجود، لا الموجود → مُشار إليه)، وتظل التستات خضراء —
ويفقد كل مستخدم عربي البودكاست عند النشر التالي، بصمت.

المفتاح الأوّلي هو `(lesson_id, kind, language)`: لغة واحدة لكل نوع لكل درس.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "docs" / "lesson_index.json"


def _base_lang(code: str | None) -> str:
    """'ar_eg' → 'ar'. الفيديو يعلن `ar_eg` والبودكاست `ar` — وهما لغة واحدة."""
    return (code or "").strip().lower().replace("-", "_").split("_")[0] or "ar"


def upsert_media(lesson_id: str, kind: str, entry: dict,
                 index_path: Path | None = None) -> str:
    """يُدرج أو يستبدل مدخلًا واحدًا. يرجّع 'inserted' أو 'replaced' أو 'no-lesson'.

    `entry` يجب أن يحمل `file` و`language` — الفهرس بلا لغة هو ما جعل بودكاستًا
    عربيًّا يُقدَّم لمستخدمي الإنجليزية على أنه إنجليزي.
    """
    if not entry.get("file"):
        raise ValueError("entry بلا file")
    if not (entry.get("language") or "").strip():
        raise ValueError("entry بلا language — الفهرس بلا لغة يُخمَّن، والتخمين أخطأ من قبل")

    path = index_path or INDEX_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    lang = _base_lang(entry.get("language"))

    for lesson in data.get("lessons", []):
        if lesson.get("lesson_id") != lesson_id:
            continue
        bucket = lesson.setdefault("assets", {}).setdefault(kind, [])
        for i, existing in enumerate(bucket):
            if _base_lang(existing.get("language")) == lang:
                bucket[i] = {**existing, **entry}
                _write(path, data)
                return "replaced"
        bucket.append(entry)
        _write(path, data)
        return "inserted"
    return "no-lesson"


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
