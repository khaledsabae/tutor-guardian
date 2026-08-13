"""ترقية التقدّم تطابق القيد الفريد الحقيقي: (device_id, lesson_id).

`child_id` أُضيف للجدول بعد إنشائه ولم يدخل القيد الفريد، فالجدول لا يحتمل
إلا صفًا واحدًا لكل (جهاز، درس) مهما بلغ عدد الأطفال. الاستعلام كان يبحث
بـ`child_id` أيضًا، فصفٌّ يملكه أخٌ آخر يصير غير مرئي:

  * الإدراج → `UNIQUE constraint failed` → **500** لأبٍ يُتمّ درسًا. وقع
    ثماني مرات يوم 2026-08-13 بعد ترحيل نقل صفوفًا إلى الأخ الصحيح بينما
    العملاء ما زالوا لا يبعثون `child_id`.
  * التحديث → لا صف يطابق → **لا تغيير ولا خطأ**، والإتمام يضيع صامتًا.
    وهو نفس عطل البلاغ لكن بردّ 200.
"""
import pytest
from fastapi.testclient import TestClient

from app.db.init_db import get_conn
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def _session(client):
    r = client.post("/api/chat/sessions", json={"device_id": "dev-upsert"})
    assert r.status_code == 201, r.text
    return r.json()["token"]


def _child(client, token, name, age):
    r = client.post("/api/children", json={"name": name, "age_group": age},
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _lesson_id(client, token):
    """أول درس حقيقي من الفهرس — لا معرّف مخترع يرفضه الخادم بـ404.

    تفاصيل المسار تُرجع `lesson_ids` لا `lessons`؛ القراءة الخاطئة جعلت
    الاختبارين يتخطّيان بصمت فلم يثبتا شيئًا — وهو أسوأ من الفشل.
    """
    hdr = {"Authorization": f"Bearer {token}"}
    r = client.get("/api/program/paths", headers=hdr)
    assert r.status_code == 200, r.text
    paths = r.json().get("paths") or []
    assert paths, "فهرس المسارات فارغ — البيئة ناقصة لا الكود"
    for p in paths:
        d = client.get(f"/api/program/paths/{p['id']}", headers=hdr).json()
        ids = d.get("lesson_ids") or [x["id"] for x in (d.get("lessons") or [])]
        if ids:
            return ids[0]
    raise AssertionError("لا مسار يحمل دروسًا — الفهرس معطوب")


def test_sibling_owned_row_does_not_500(client):
    """الصف يخصّ أخًا، والعميل لا يبعث child_id — يجب ألا ينهار."""
    token = _session(client)
    first = _child(client, token, "الأول", "prenatal-1")
    second = _child(client, token, "الثاني", "2-3")
    lesson = _lesson_id(client, token)
    hdr = {"Authorization": f"Bearer {token}"}

    r = client.patch(f"/api/program/lessons/{lesson}/progress",
                     json={"status": "completed", "child_id": second}, headers=hdr)
    assert r.status_code == 200, r.text

    # عميل قديم: بلا child_id → يسقط على أول طفل أُنشئ، والصف يخصّ الثاني
    r = client.patch(f"/api/program/lessons/{lesson}/progress",
                     json={"status": "in_progress"}, headers=hdr)
    assert r.status_code == 200, f"انهار بدل أن يرقّي: {r.status_code} {r.text[:200]}"

    conn = get_conn()
    rows = conn.execute(
        "SELECT child_id, status FROM lesson_progress WHERE device_id='dev-upsert'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, f"القيد يسمح بصف واحد فقط، وُجد {len(rows)}"
    assert rows[0]["status"] == "in_progress", "التحديث لم يُطبَّق"
    assert rows[0]["child_id"] == second, "عميل بلا child_id يجب ألا ينقل الملكية"
    assert first != second


def test_naming_a_child_repoints_the_row(client):
    """عميل يسمّي طفله يعيد توجيه الصف إليه."""
    token = _session(client)
    a = _child(client, token, "أ", "prenatal-1")
    b = _child(client, token, "ب", "2-3")
    lesson = _lesson_id(client, token)
    hdr = {"Authorization": f"Bearer {token}"}

    client.patch(f"/api/program/lessons/{lesson}/progress",
                 json={"status": "in_progress", "child_id": a}, headers=hdr)
    r = client.patch(f"/api/program/lessons/{lesson}/progress",
                     json={"status": "completed", "child_id": b}, headers=hdr)
    assert r.status_code == 200, r.text

    conn = get_conn()
    rows = conn.execute(
        "SELECT child_id, status, completed_at FROM lesson_progress "
        "WHERE device_id='dev-upsert'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["child_id"] == b
    assert rows[0]["status"] == "completed"
    assert rows[0]["completed_at"]
