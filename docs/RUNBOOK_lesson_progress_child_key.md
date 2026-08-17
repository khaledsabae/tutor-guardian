# Runbook — ترحيل `lesson_progress` إلى مفتاح لكل طفل

**الحالة:** الكود جاهز ومُختبَر على الفرع `fix/usability-p0`. **الترحيل لم يُنفَّذ
على الإنتاج بعد.** النسخة الاحتياطية مأخوذة.

---

## لماذا هذا ملف منفصل ولم يُنفَّذ ضمن الجولة

**الترحيل لا يمكن فصله عن النشر.** جُرِّب الاحتمالان، والنتيجة مُثبَتة لا مُستنتَجة:

| الترتيب | ما يحدث |
|---|---|
| ترحيل القاعدة **قبل** نشر الكود | الـhandler المنشور حاليًا يُحدِّث بـ`WHERE device_id = ? AND lesson_id = ?` ويكتب `child_id`. على المخطّط الجديد يطابق **صفَّي الأخوين معًا** ويمنحهما نفس `child_id` → `IntegrityError: UNIQUE constraint failed: lesson_progress.device_id, lesson_progress.child_id, lesson_progress.lesson_id` → **500 لكل إتمام في أسرة متعددة الأطفال** |
| نشر الكود **قبل** ترحيل القاعدة | الـhandler الجديد يبحث بـ`child_id` فلا يرى صف الأخ، فيُدرج، فيصطدم بالقيد ثنائي الأعمدة → **نفس أعطال ١٣ أغسطس بالضبط** |

فلا ترتيب آمن بينهما كخطوتين. الترحيل مصمَّم ليعمل **داخل إقلاع التطبيق**
(`init_db` → `_ensure_lesson_progress_child_key`)، فيتمّان معًا في نافذة الإقلاع.

**النتيجة العملية:** تنفيذ الترحيل = نشر الفرع. ودفع `main` في هذا المستودع
نشرٌ إنتاجي تلقائي — وهو الحدّ الذي وُضع في الخطة المعتمدة، فتُوقّف الجولة هنا
لمراجعتك.

---

## النسخة الاحتياطية (مأخوذة بالفعل)

```
/root/db-backups/lesson_progress_pre_migration_20260817T105024Z.db
```

- الحجم: **18,714,624 بايت** · `PRAGMA integrity_check` = **ok**
- `lesson_progress` = **2,443** صفًا · `child_profiles` = **3,795**
- تحمل المفتاح القديم `UNIQUE (device_id, lesson_id)` — أي أنها فعلًا ما قبل الترحيل
- أُخذت بـ`sqlite3.backup()` لا `cp` — القاعدة في وضع WAL والنسخ الخام عليها يكسر

> لو مرّ وقت طويل قبل التنفيذ، **خُذ نسخة جديدة**؛ هذه تُصبح قديمة بعدد الصفوف
> التي كُتبت بعدها.

---

## خط الأساس قبل الترحيل (لمقارنة الأثر)

| المقياس | القيمة |
|---|---|
| صفوف `lesson_progress` | 2,443 |
| `completed` / `in_progress` | 572 / 1,871 |
| `child_id IS NULL` | 20 |
| `child_id = 0` | 13 |
| أجهزة لها تقدّم | 1,283 |
| صفوف على أجهزة متعددة الأطفال | 541 |

بعد الترحيل: **العدد الكلي لا يتغيّر** (٢,٤٤٣). الترحيل توسيعٌ للمفتاح لا دمج —
المفتاح القديم يضمن صفًا واحدًا لكل (جهاز، درس) فلا تصادم في الخروج منه. الـ٢٠
صفًا ذات `child_id IS NULL` تُطوى على `0` فتصير `zero_child = 33`.

---

## التنفيذ

```bash
ssh root@72.62.44.131 "cd /root/tutor-guardian && git pull && docker compose up -d --build tg_backend"
```

الترحيل يجري تلقائيًا في الإقلاع. راقب:

```bash
ssh root@72.62.44.131 "docker logs --tail 80 tg_backend"
```

---

## التحقق بالأثر — لا بكود الخروج

**١) القيد نفسه تغيّر:**

```bash
ssh root@72.62.44.131 "docker exec tg_backend python -c \"
from app.db.init_db import get_conn
c = get_conn()
sql = c.execute(\\\"SELECT sql FROM sqlite_master WHERE name='lesson_progress'\\\").fetchone()[0]
print(' '.join(sql.split()))
\""
```
يجب أن يحوي `UNIQUE (device_id, child_id, lesson_id)`.

**٢) لا صف ضاع:**

```bash
ssh root@72.62.44.131 "docker exec tg_backend python -c \"
from app.db.init_db import get_conn
c = get_conn()
print('rows:', c.execute('SELECT COUNT(*) FROM lesson_progress').fetchone()[0], '(expect 2443)')
print('by_status:', [tuple(r) for r in c.execute('SELECT status, COUNT(*) FROM lesson_progress GROUP BY status')])
print('null_child:', c.execute('SELECT COUNT(*) FROM lesson_progress WHERE child_id IS NULL').fetchone()[0], '(expect 0)')
print('zero_child:', c.execute('SELECT COUNT(*) FROM lesson_progress WHERE child_id = 0').fetchone()[0], '(expect 33)')
\""
```

**٣) الأثر المقصود — طفلان يُتمّان نفس الدرس ويحتفظ كلٌّ بإتمامه.** هذا هو
الاختبار الوحيد الذي يُثبت أن العطل المُبلَّغ عنه انتهى. لا تكتفِ بالخطوتين أعلاه:

```bash
ssh root@72.62.44.131 "docker exec tg_backend python -m pytest tests/test_progress_upsert_key.py tests/test_lesson_progress_migration.py -q"
```

**٤) على جهاز حقيقي** (الحُكم النهائي): أسرة بطفلين، أتمِم نفس الدرس للاثنين،
ثم افتح تقدّم كلٍّ منهما — يجب أن يظهر الدرس مكتملًا عند **الاثنين**.

---

## التراجع

```bash
ssh root@72.62.44.131 "
docker compose stop tg_backend
docker cp /root/db-backups/lesson_progress_pre_migration_20260817T105024Z.db \
  tg_backend:/app/ops/conversations.db
cd /root/tutor-guardian && git revert <sha> && docker compose up -d --build tg_backend
"
```

⚠️ استرجاع القاعدة **يفقد كل ما كُتب بعد وقت النسخة** (محادثات، ملاحظات، تقدّم).
لو مضى وقت طويل، فالأصحّ التراجع عن الكود وحده وترك القاعدة مُرحَّلة — الكود
القديم على المخطّط الجديد يُنتج 500 كما في الجدول أعلاه، فهذا **ليس** مسار تراجع
صالحًا. عمليًا: التراجع يعني استرجاع الاثنين معًا وبسرعة، أو المضيّ قُدُمًا
وإصلاح ما ينكشف.

---

## بعد التنفيذ

قيد مؤرَّخ في `publishing-center/OPERATIONS_LOG.md` بالصيغة المعتمدة: التاريخ،
ما تغيّر، السبب (#fb_a1325670 — ١٩١ جهازًا متعدد الأطفال يفقد إتمامات)، مسار
النسخة الاحتياطية، ونتيجة التحقق بالأثر الفعلية لا المتوقَّعة.
