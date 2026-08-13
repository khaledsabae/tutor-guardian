"""وثائق الحوكمة لا تدخل فهرس الاسترجاع — وتبقى على القرص.

قياس 2026-08-13 على شهر من أسئلة الآباء الحقيقية: 51% من الوحدات المسترجَعة
حُكم عليها بـ«لا صلة»، و77 من كل 100 سؤال لم تجد ما يخدمها. وربع الكوربوس
(325 وحدة) وثائق موجَّهة للحكومات وشركات الاتصالات — «تمويل المعدات»،
«المحاكم»، «المشاريع التجريبية» — تتنافس على الخانات الأربع التي يرجعها
الاسترجاع. أب يسأل عن طفل يخاف النوم وحده كان ينافسه 127 وحدة من دليل صناعي.
"""
import json
from pathlib import Path

from app.services.knowledge_loader import (
    EXCLUDED_SOURCES,
    BASE_DIR,
    load_default_knowledge_units,
)

UNITS_DIR = BASE_DIR / "units"


def _on_disk() -> list[dict]:
    out = []
    for f in sorted(UNITS_DIR.glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001, S112
            continue
    return out


def test_excluded_sources_are_absent_from_the_index():
    """`KnowledgeUnit` لا يحمل `source_file`، فالمطابقة بالمعرّف من القرص."""
    excluded_ids = {
        d.get("id") for d in _on_disk()
        if (d.get("source_file") or "") in EXCLUDED_SOURCES
    }
    assert excluded_ids, "لم يُطابَق أي ملف — القائمة أو المسار خطأ"

    loaded = load_default_knowledge_units()
    assert loaded, "المُحمِّل لم يرجع شيئًا — تحقّق من مسار الوحدات"
    leaked = [u.id for u in loaded if u.id in excluded_ids]
    assert not leaked, f"{len(leaked)} وحدة مستبعَدة تسرّبت إلى الفهرس"


def test_the_files_are_still_on_disk():
    """الاستبعاد من الفهرس لا حذف — الملفات تبقى في نطاق حارس السلامة."""
    disk = _on_disk()
    excluded = [d for d in disk if (d.get("source_file") or "") in EXCLUDED_SOURCES]
    assert len(excluded) > 300, (
        f"عدد الملفات المستبعَدة على القرص {len(excluded)} — "
        "لو صار صفرًا فقد حُذفت بدل أن تُستبعد"
    )


def test_exclusion_does_not_empty_any_domain():
    """التنظيف يجب ألا يُفرغ مجالًا — cyber كان أكثر المجالات تأثرًا."""
    loaded = load_default_knowledge_units()
    by_domain: dict[str, int] = {}
    for u in loaded:
        by_domain[u.domain] = by_domain.get(u.domain, 0) + 1
    for domain in ("islamic_parenting", "medical", "cyber", "development", "aqeedah"):
        assert by_domain.get(domain, 0) > 0, f"مجال {domain} صار بلا وحدات"
    # cyber فقد 200 وحدة من أصل 253؛ لو نزل تحت هذا فقد أُفرِط في الاستبعاد
    assert by_domain["cyber"] >= 40, by_domain


def test_excluded_list_matches_real_files():
    """اسم ملف مصدر خاطئ في القائمة = استبعاد صامت لا يستبعد شيئًا."""
    on_disk_sources = {d.get("source_file") or "" for d in _on_disk()}
    unknown = [s for s in EXCLUDED_SOURCES if s not in on_disk_sources]
    assert not unknown, f"قيم لا تطابق أي ملف مصدر: {unknown}"
