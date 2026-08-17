"""ترقية التقدّم تطابق القيد الفريد: (device_id, child_id, lesson_id).

القيد في الإنتاج كان (device_id, lesson_id): صفٌّ واحد لكل (جهاز، درس) مهما
بلغ عدد الأطفال. والقراءة تفلتر `child_id IN (?, 0)`. فلمّا يُتمّ الأخ الثاني
نفس الدرس، لا يُنشأ له صف — بل يُعاد توجيه صف أخيه إليه، فيختفي إتمام الأول
من تقدّمه. وهذا هو «أتمم الدرس ولا يتم تسجيل التقدم» (#fb_a1325670، 1.0.40+85)
لكل أسرة فيها أكثر من طفل: ٣٠٥ أجهزة، ١٩١ منها لها صفوف تقدّم.

إصلاح ١٣ أغسطس صحّح *لمن* يُنسب الإتمام، ولم يستطع إنشاء الصف الثاني لأن
القيد يمنعه. الترحيل `_ensure_lesson_progress_child_key` يوسّع القيد، وهذه
الاختبارات تثبّت السلوك الجديد:

  * كل طفل يملك صفّه — إتمام الأخ لا يمحو إتمام أخيه.
  * العميل القديم (بلا `child_id`) لا يزال لا ينهار ولا ينقل ملكية.
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


def _rows(lesson):
    conn = get_conn()
    rows = conn.execute(
        "SELECT child_id, status, completed_at FROM lesson_progress "
        "WHERE device_id='dev-upsert' AND lesson_id = ? ORDER BY child_id",
        (lesson,),
    ).fetchall()
    conn.close()
    return rows


def test_the_unique_key_is_per_child(client):
    """القيد نفسه — لا سلوكه — يحمل child_id."""
    conn = get_conn()
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='lesson_progress'"
    ).fetchone()[0]
    conn.close()
    normalised = " ".join(sql.split()).lower()
    assert "unique (device_id, child_id, lesson_id)" in normalised, (
        "القيد لم يُرحَّل — الأخ سيمحو أخاه:\n" + sql
    )


def test_siblings_each_keep_their_own_completion(client):
    """العطل المُبلَّغ عنه: إتمام الأخ الثاني كان يمحو إتمام الأول."""
    token = _session(client)
    a = _child(client, token, "أ", "prenatal-1")
    b = _child(client, token, "ب", "2-3")
    lesson = _lesson_id(client, token)
    hdr = {"Authorization": f"Bearer {token}"}

    for child in (a, b):
        r = client.patch(f"/api/program/lessons/{lesson}/progress",
                         json={"status": "completed", "child_id": child},
                         headers=hdr)
        assert r.status_code == 200, r.text

    rows = _rows(lesson)
    assert len(rows) == 2, f"طفلان أتمّا الدرس — يجب صفّان، وُجد {len(rows)}"
    assert {r["child_id"] for r in rows} == {a, b}
    assert all(r["status"] == "completed" for r in rows), "أحدهما فقد إتمامه"
    assert all(r["completed_at"] for r in rows)


def test_each_child_reads_back_their_own_progress(client):
    """التحقق بالأثر: كل طفل يرى إتمامه في المسار الذي يقرأه التطبيق."""
    token = _session(client)
    a = _child(client, token, "أ", "prenatal-1")
    b = _child(client, token, "ب", "2-3")
    lesson = _lesson_id(client, token)
    hdr = {"Authorization": f"Bearer {token}"}

    for child in (a, b):
        client.patch(f"/api/program/lessons/{lesson}/progress",
                     json={"status": "completed", "child_id": child}, headers=hdr)

    for child in (a, b):
        r = client.get(f"/api/children/{child}/progress", headers=hdr)
        assert r.status_code == 200, r.text
        done = [
            x["lesson_id"] for x in r.json().get("lessons", [])
            if x["status"] == "completed"
        ]
        assert lesson in done, f"الطفل {child} لا يرى إتمامه — الصف ضاع"


def test_sibling_owned_row_does_not_500(client):
    """العميل القديم بلا child_id: لا انهيار ولا نقل ملكية."""
    token = _session(client)
    first = _child(client, token, "الأول", "prenatal-1")
    second = _child(client, token, "الثاني", "2-3")
    lesson = _lesson_id(client, token)
    hdr = {"Authorization": f"Bearer {token}"}

    r = client.patch(f"/api/program/lessons/{lesson}/progress",
                     json={"status": "completed", "child_id": second}, headers=hdr)
    assert r.status_code == 200, r.text

    # عميل قديم: بلا child_id → يسقط على أول طفل أُنشئ
    r = client.patch(f"/api/program/lessons/{lesson}/progress",
                     json={"status": "in_progress"}, headers=hdr)
    assert r.status_code == 200, f"انهار بدل أن يرقّي: {r.status_code} {r.text[:200]}"

    rows = {row["child_id"]: row for row in _rows(lesson)}
    assert rows[second]["status"] == "completed", "إتمام الثاني ضاع تحت عميل قديم"
    assert rows[first]["status"] == "in_progress", "العميل القديم لم يُسجَّل"


def test_naming_a_child_gets_its_own_row_not_the_siblings(client):
    """عميل يسمّي طفله يحصل على صفّه هو — لا يعيد توجيه صف أخيه.

    كان هذا الاختبار يثبّت العكس (`len(rows) == 1` والصف ينتقل إلى الأخير)،
    وهو بالضبط السلوك الذي أنتج البلاغ.
    """
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

    rows = {row["child_id"]: row for row in _rows(lesson)}
    assert set(rows) == {a, b}, "الصف انتقل بدل أن يُنشأ صف جديد"
    assert rows[a]["status"] == "in_progress", "تقدّم أ تغيّر بفعل ب"
    assert rows[b]["status"] == "completed"
    assert rows[b]["completed_at"]
