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

from app.db.init_db import _ensure_lesson_progress_child_key


_OLD_PROD_SCHEMA = """
    CREATE TABLE lesson_progress (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id    TEXT NOT NULL,
        lesson_id    TEXT NOT NULL,
        path_id      TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'not_started',
        started_at   TEXT,
        completed_at TEXT,
        updated_at   TEXT NOT NULL DEFAULT (datetime('now')),
        score        INTEGER,
        child_id     INTEGER,
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
