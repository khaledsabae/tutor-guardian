"""نصائح اليوم تدخل فهرس الاسترجاع — وإلا لم يجد follow-up عليها مصدرًا.

البلاغ الحي (تقرير فجوات المعرفة): أولياء يسألون عن نصيحة وصلتهم ("بخصوص
نصيحة اليوم: ... إزاي أطبقها عملي؟") والاسترجاع يردّ وحدات لا صلة لها —
لأن نصّ النصيحة نفسه لم يكن في الفهرس إطلاقًا، رغم أن الـAPI يعرضها.

`DEFAULT_KB_DIRS` كان لا يشمل `curriculum/daily_tips`، فلم تُضمَّن أيّ من
الـ210 نصيحة المعروضة للمستخدمين.
"""
from app.services.knowledge_loader import (
    DAILY_TIPS_DIR,
    load_default_knowledge_units,
)


def _tips_on_disk_ids() -> set[str]:
    import json

    ids = set()
    for f in sorted(DAILY_TIPS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001, S112
            continue
        # نفس منطق الـAPI: المفتاح الغائب = منشور، والصريح False وحده مسودّة.
        if data.get("is_published", True) and (data.get("id") or "").strip():
            if (data.get("text") or "").strip():
                ids.add(data["id"])
    return ids


def test_daily_tips_dir_is_the_one_parents_see():
    assert DAILY_TIPS_DIR.exists(), f"مجلد النصائح غائب: {DAILY_TIPS_DIR}"
    ids = _tips_on_disk_ids()
    assert len(ids) >= 200, (
        f"عدد النصائح المنشورة على القرص {len(ids)} — المتوقع ~210؛ "
        "لو نزل كثيرًا فالمجلد أو الشرط اتغيّر"
    )


def test_every_published_tip_is_indexed():
    """كل نصيحة يراها ولي الأمر لازم تكون قابلة للاسترجاع بنصّها."""
    disk_ids = _tips_on_disk_ids()
    loaded = load_default_knowledge_units()
    loaded_tip = {u.id: u for u in loaded if u.id.startswith("tip_")}

    missing = disk_ids - set(loaded_tip)
    assert not missing, (
        f"{len(missing)} نصيحة معروضة في الـAPI لكنها خارج الفهرس: "
        f"{sorted(missing)[:5]}"
    )

    # سلامة الحقول اللي الاسترجاع بيبني عليها الفيكتور والفلاتر.
    empty_body = [uid for uid, u in loaded_tip.items() if not u.text_simplified]
    assert not empty_body, f"نصائح بلا نصّ surface: {empty_body[:5]}"

    no_domain = [uid for uid, u in loaded_tip.items() if not u.domain]
    assert not no_domain, f"نصائح بلا domain: {no_domain[:5]}"


def test_tip_surface_text_reaches_the_embedding():
    """نصّ النصيحة (ما رآه الوالد) يجب أن يكون داخل embedding_text.

    وإلا حتى وهي مفهرسة لن يطابقها سؤال يقتبس النصيحة — نفس عيب الكوربوس
    الأصلي الذي عالجه `topic_header` للوحدات العادية.
    """
    loaded = load_default_knowledge_units()
    tips = [u for u in loaded if u.id.startswith("tip_")]
    assert tips, "لا نصائح في الحمولة"
    lacking = [u.id for u in tips if u.text_simplified not in u.embedding_text]
    assert not lacking, f"{len(lacking)} نصيحة نصّها خارج الفيكتور: {lacking[:5]}"


def test_tips_keep_their_backing_unit_link():
    """`unit_id` (الوحدة الأم التي وُلدت منها النصيحة) يُحفظ في reference_info.

    ده ما يمكّن follow-up من الوصول للنصيحة والوحدة السندية معًا.
    """
    loaded = load_default_knowledge_units()
    linked = [
        u for u in loaded
        if u.id.startswith("tip_") and (u.source_meta or {}).get("backing_unit_id")
    ]
    assert linked, "لا نصيحة تحمل رابط الوحدة الأم — source_meta/backing_unit_id ضاع"
    for u in linked:
        meta = u.source_meta or {}
        assert u.reference_info == meta["backing_unit_id"], (
            f"{u.id}: reference_info لا يطابق backing_unit_id"
        )
