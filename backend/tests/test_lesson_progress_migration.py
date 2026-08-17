"""الترحيل نفسه: من مفتاح الإنتاج ذي العمودين إلى مفتاح لكل طفل.

الاختبارات في `test_progress_upsert_key.py` تشتغل على قاعدة نظيفة، فتثبت
السلوك بعد الترحيل ولا تمرّ بالترحيل أصلًا. وهنا الخطر الحقيقي: قاعدة
الإنتاج فيها ٢٬٤٤٣ صفًا حيًّا، والقيد يُبنى بإعادة إنشاء الجدول ونسخه —
لا بـ`ALTER`. فالبيانات تُنقل بيد، ويد تُخطئ.

ثلاثة أشكال يجب أن يبتلعها الترحيل:
  * شكل الإنتاج: `UNIQUE (device_id, lesson_id)` — توسيع لا تصادم فيه.
  * الصفوف القديمة بـ`child_id IS NULL` — تُطوى على 0 لأن NULL في sqlite
    لا يساوي NULL، فصفّان بلا طفل يمرّان من القيد الجديد.
  * شكل القاعدة النظيفة رباعي الأعمدة — يحتمل صفّين يختلفان في `path_id`
    فقط، فيُبقى الأبعد تقدّمًا.
"""
import sqlite3

import pytest

from app.db.init_db import _ensure_lesson_progress_child_key


# منسوخ حرفيًا من `sqlite_master` على الإنتاج يوم 2026-08-17 — لا مكتوب من
# `CREATE TABLE` في init_db.py. النسخة الأولى من هذا الملف كُتبت من المخطّط
# المُعلَن فاخترعت عمود `score`، والإنتاج لا يملكه. فمرّت الاختبارات كلها
# ووقع الترحيل على الخادم بـ`no such column: score`. الفرق بين ما نظنّه
# مخطّطنا وما هو عليه فعلًا هو بالضبط ما يجب أن يُختبَر.
_OLD_PROD_SCHEMA = """
    CREATE TABLE lesson_progress (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id    TEXT NOT NULL,
        lesson_id    TEXT NOT NULL,
        path_id      TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'not_started',
        started_at   TEXT,
        completed_at TEXT,
        updated_at   TEXT NOT NULL DEFAULT (datetime('now')), child_id INTEGER,
        UNIQUE (device_id, lesson_id)
    );
"""

_FRESH_FOUR_COL_SCHEMA = """
    CREATE TABLE lesson_progress (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id    TEXT NOT NULL,
        child_id     INTEGER NOT NULL,
        path_id      TEXT NOT NULL,
        lesson_id    TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'not_started',
        started_at   TEXT,
        completed_at TEXT,
        score        INTEGER,
        updated_at   TEXT,
        UNIQUE (device_id, child_id, path_id, lesson_id)
    );
"""


def _conn(schema):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(schema)
    return c


def _key_of(conn):
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='lesson_progress'"
    ).fetchone()[0]
    return " ".join(sql.split()).lower()


def test_production_shape_migrates_and_keeps_every_row():
    conn = _conn(_OLD_PROD_SCHEMA)
    conn.executemany(
        "INSERT INTO lesson_progress "
        "(device_id, lesson_id, path_id, status, started_at, completed_at,"
        " updated_at, child_id) VALUES (?,?,?,?,?,?,?,?)",
        [
            ("dev1", "l1", "p1", "completed", "t0", "t1", "t1", 7),
            ("dev1", "l2", "p1", "in_progress", "t0", None, "t0", 7),
            ("dev2", "l1", "p1", "completed", "t0", "t1", "t1", 9),
        ],
    )
    conn.commit()

    _ensure_lesson_progress_child_key(conn)

    assert "unique (device_id, child_id, lesson_id)" in _key_of(conn)
    rows = conn.execute(
        "SELECT device_id, child_id, lesson_id, status, completed_at "
        "FROM lesson_progress ORDER BY device_id, lesson_id"
    ).fetchall()
    assert len(rows) == 3, "الترحيل أسقط صفوفًا"
    assert [tuple(r) for r in rows] == [
        ("dev1", 7, "l1", "completed", "t1"),
        ("dev1", 7, "l2", "in_progress", None),
        ("dev2", 9, "l1", "completed", "t1"),
    ]


def test_null_child_ids_fold_onto_zero_not_into_duplicates():
    """NULL لا يساوي NULL في sqlite — لولا الطيّ لمرّ صفّان لنفس الدرس."""
    conn = _conn(_OLD_PROD_SCHEMA)
    conn.executemany(
        "INSERT INTO lesson_progress "
        "(device_id, lesson_id, path_id, status, updated_at, child_id) "
        "VALUES (?,?,?,?,?,?)",
        [
            ("dev1", "l1", "p1", "completed", "t1", None),
            ("dev1", "l2", "p1", "completed", "t1", None),
        ],
    )
    conn.commit()

    _ensure_lesson_progress_child_key(conn)

    rows = conn.execute(
        "SELECT child_id, lesson_id FROM lesson_progress ORDER BY lesson_id"
    ).fetchall()
    assert [tuple(r) for r in rows] == [(0, "l1"), (0, "l2")]


def test_after_migration_two_children_can_hold_the_same_lesson():
    """الغرض كله: صفّان لنفس الدرس لطفلين — كان القيد يمنعه."""
    conn = _conn(_OLD_PROD_SCHEMA)
    conn.execute(
        "INSERT INTO lesson_progress "
        "(device_id, lesson_id, path_id, status, updated_at, child_id) "
        "VALUES ('dev1','l1','p1','completed','t1',7)"
    )
    conn.commit()

    _ensure_lesson_progress_child_key(conn)

    conn.execute(
        "INSERT INTO lesson_progress "
        "(device_id, child_id, lesson_id, path_id, status, updated_at) "
        "VALUES ('dev1',9,'l1','p1','completed','t2')"
    )
    conn.commit()
    rows = conn.execute(
        "SELECT child_id FROM lesson_progress WHERE lesson_id='l1' ORDER BY child_id"
    ).fetchall()
    assert [r["child_id"] for r in rows] == [7, 9]


def test_four_column_shape_keeps_the_furthest_along_row():
    """صفّان يختلفان في path_id فقط — يُبقى الإتمام لا البداية."""
    conn = _conn(_FRESH_FOUR_COL_SCHEMA)
    conn.executemany(
        "INSERT INTO lesson_progress "
        "(device_id, child_id, path_id, lesson_id, status, completed_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            ("dev1", 7, "p_old", "l1", "in_progress", None, "t0"),
            ("dev1", 7, "p_new", "l1", "completed", "t1", "t1"),
        ],
    )
    conn.commit()

    _ensure_lesson_progress_child_key(conn)

    rows = conn.execute(
        "SELECT path_id, status, completed_at FROM lesson_progress"
    ).fetchall()
    assert len(rows) == 1, "المفتاح الثلاثي يحتمل صفًا واحدًا لهذا الدرس"
    assert rows[0]["status"] == "completed", "أُبقي الصف الأقل تقدّمًا"
    assert rows[0]["completed_at"] == "t1"


def test_migration_is_idempotent():
    conn = _conn(_OLD_PROD_SCHEMA)
    conn.execute(
        "INSERT INTO lesson_progress "
        "(device_id, lesson_id, path_id, status, updated_at, child_id) "
        "VALUES ('dev1','l1','p1','completed','t1',7)"
    )
    conn.commit()

    _ensure_lesson_progress_child_key(conn)
    first = _key_of(conn)
    _ensure_lesson_progress_child_key(conn)

    assert _key_of(conn) == first
    assert conn.execute("SELECT COUNT(*) FROM lesson_progress").fetchone()[0] == 1
    # وجدول العمل المؤقّت لا يبقى وراءه
    left = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='lesson_progress_new'"
    ).fetchone()
    assert left is None


def test_indexes_survive_the_swap():
    """DROP TABLE يأخذ فهارسه معه — لولا إعادة البناء لصارت القراءة مسحًا."""
    conn = _conn(_OLD_PROD_SCHEMA)
    _ensure_lesson_progress_child_key(conn)
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='lesson_progress'"
        ).fetchall()
    }
    assert "ix_lesson_progress_device_child" in names
    assert "ix_lesson_progress_device" in names
    assert "ix_lesson_progress_path_device" in names


def test_missing_score_column_is_not_assumed():
    """الإنتاج بلا `score`؛ الترحيل يقرأ الأعمدة ولا يفترضها.

    هذا هو العطل الذي أسقط النشر 32022710188: قائمة أعمدة مكتوبة باليد من
    مخطّط init_db سمّت عمودًا لا وجود له على الخادم.
    """
    conn = _conn(_OLD_PROD_SCHEMA)
    assert "score" not in {r[1] for r in conn.execute("PRAGMA table_info(lesson_progress)")}
    conn.execute(
        "INSERT INTO lesson_progress "
        "(device_id, lesson_id, path_id, status, updated_at, child_id) "
        "VALUES ('d','l','p','completed','t1',7)"
    )
    conn.commit()

    _ensure_lesson_progress_child_key(conn)

    assert "unique (device_id, child_id, lesson_id)" in _key_of(conn)
    row = conn.execute("SELECT child_id, status, score FROM lesson_progress").fetchone()
    assert (row["child_id"], row["status"], row["score"]) == (7, "completed", None)


def test_a_failed_attempt_leaves_no_debris_and_the_retry_works():
    """الإصلاح الثاني: المحاولة الفاشلة كانت تُبقي `lesson_progress_new`.

    `executescript` يعمل COMMIT قبل تنفيذه، فالجدول نصف المبني كان ينجو من
    الانهيار ويحوّل كل إعادة محاولة إلى `table lesson_progress_new already
    exists` — وهي الحلقة التي دار فيها الخادم حتى تراجع النشر.
    """
    conn = _conn(_OLD_PROD_SCHEMA)
    conn.execute(
        "INSERT INTO lesson_progress "
        "(device_id, lesson_id, path_id, status, updated_at, child_id) "
        "VALUES ('d','l','p','completed','t1',7)"
    )
    conn.commit()

    # حطام محاولة سابقة، كما وُجد على الإنتاج بالضبط (صفر صفوف)
    conn.execute("CREATE TABLE lesson_progress_new (id INTEGER PRIMARY KEY)")
    conn.commit()

    _ensure_lesson_progress_child_key(conn)

    assert "unique (device_id, child_id, lesson_id)" in _key_of(conn)
    assert conn.execute("SELECT COUNT(*) FROM lesson_progress").fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='lesson_progress_new'"
    ).fetchone()[0] == 0


class _CrashingConnection(sqlite3.Connection):
    """ينهار عند `DROP TABLE lesson_progress` — أي في منتصف التبديل بالضبط.

    `sqlite3.Connection.execute` للقراءة فقط فلا يُرقَّع بـmonkeypatch؛
    الوراثة هي الطريق.
    """

    crash_on = "DROP TABLE LESSON_PROGRESS"
    armed = True

    def execute(self, sql, *a, **kw):
        if self.armed and sql.strip().upper().startswith(self.crash_on):
            raise sqlite3.OperationalError("simulated crash mid-swap")
        return super().execute(sql, *a, **kw)


def test_a_broken_copy_rolls_back_whole():
    """لو انهار النسخ في المنتصف، الجدول الأصلي يبقى كما هو ولا حطام."""
    conn = sqlite3.connect(":memory:", factory=_CrashingConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript(_OLD_PROD_SCHEMA)
    conn.executescript(
        "INSERT INTO lesson_progress "
        "(device_id, lesson_id, path_id, status, updated_at, child_id) "
        "VALUES ('d','l','p','completed','t1',7);"
    )

    with pytest.raises(sqlite3.OperationalError):
        _ensure_lesson_progress_child_key(conn)

    conn.armed = False
    # الأصل سليم بمفتاحه القديم، ولا جدول عمل متروك
    assert conn.execute("SELECT COUNT(*) FROM lesson_progress").fetchone()[0] == 1
    assert "unique (device_id, lesson_id)" in _key_of(conn)
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='lesson_progress_new'"
    ).fetchone()[0] == 0

    # ثم تنجح إعادة المحاولة — وهو ما لم يكن يحدث على الإنتاج
    _ensure_lesson_progress_child_key(conn)
    assert "unique (device_id, child_id, lesson_id)" in _key_of(conn)
    assert conn.execute("SELECT COUNT(*) FROM lesson_progress").fetchone()[0] == 1
