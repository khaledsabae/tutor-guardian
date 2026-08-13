# دليل التشغيل — المربي الذكي (Ops Runbook)

> **لمن هذا الدليل؟** لمتطوع ثانٍ ينضم للمساعدة في تشغيل «المربي الذكي» مستقبلًا. يشرح البنية والتشغيل اليومي والتعامل مع الأعطال **دون أن يحتوي أي سر** (توكنز/مفاتيح/باسوردات) — الأسرار تُطلب من خالد مباشرة (§9).
>
> هذا الدليل ينفّذ البند §5.3 من `plans/growth-master-plan-2026-07.md`: «توثيق تشغيلي يسمح لمتطوع ثانٍ بالمساعدة مستقبلًا دون تسليمه أسرار البنية».
>
> **آخر تحديث:** 2026-07-16. الجداول الزمنية والمسارات هنا تُوثّق الحالة وقت الكتابة — المرجع الحي للجدولة هو `~/projects/CRONS.md` و`pcc list`.

---

## 0) دستور المنتج — غير قابل للتفاوض

- التطبيق **مجاني بالكامل مدى الحياة، بلا إعلانات، بلا مشتريات داخلية، بلا اشتراكات — عمل لوجه الله.**
- ممنوع اقتراح أو إدخال أي شكل من أشكال الـmonetization، مهما كانت التكاليف.
- الرافعة الاقتصادية الوحيدة المسموحة: **خفض تكلفة التشغيل** (كاش الإجابات، التوليد المسبق، الحدود العادلة، الاستدلال المحلي) — راجع §5 في خطة النمو.
- استمرارية التطبيق جزء من الأمانة: أي قرار تشغيلي يوازن بين الجودة والتكلفة، لا بين الجودة والإيراد.

---

## 1) نظرة معمارية عامة

```
المستخدم (تطبيق أندرويد Flutter)
        │ HTTPS
        ▼
Cloudflare ──► analytics_nginx (على الـVPS) ──► tg_backend (FastAPI في Docker)
   alsaba.cloud / tg-api.alsaba.cloud                │
                                                     ├─► ChromaDB (فهرس RAG — volume داخل Docker)
                                                     ├─► SQLite (sessions.db + conversations.db — volume داخل Docker)
                                                     │
                                                     ├─► Ollama على tg-home (عبر Tailscale) ← المسار الأساسي للاستدلال
                                                     └─► DeepSeek السحابي ← صمام أمان أخير بسقف توكنز شهري
```

### 1.1 المكونات

| المكوّن | أين يعيش | ملاحظات |
|---|---|---|
| **الباكند** (FastAPI + RAG + Guardrails) | حاوية `tg_backend` على الـVPS، خلف `analytics_nginx` (شبكة Docker مشتركة `analytics-platform_production_network`) ثم Cloudflare | الدومينات: `alsaba.cloud` (صفحات عامة/SEO) و`tg-api.alsaba.cloud` (API). لا يوجد منفذ مكشوف على المضيف — nginx يصل للحاوية بالاسم |
| **الاستدلال الأساسي** | Ollama على خادم `tg-home` المنزلي، يصل إليه الباكند عبر Tailscale | تكلفة ثابتة مهما زاد الاستخدام + ميزة الخصوصية. النموذج الحالي من عائلة `tg-tutor:vN` |
| **صمام الأمان السحابي** | DeepSeek API | لا يُستدعى **إلا** عند سقوط السلسلة المحلية بالكامل. فلاج `DEEPSEEK_FALLBACK_ENABLED` + سقف شهري صارم fail-closed `DEEPSEEK_FALLBACK_MONTHLY_TOKEN_CAP` (10M توكن). الميزانية تُحسب من جدول `llm_calls` |
| **مخزن المتجهات** | ChromaDB في volume باسم `tg_chroma` | ⚠️ راجع §3.2 — خطر ترقية 0.x→1.x |
| **قواعد SQLite** | volume باسم `tg_sessions` مركّب على `/app/ops` | راجع §3.1 |
| **تطبيق الموبايل** | Flutter (المجلد `mobile/`) — التوزيع عبر Google Play | إصداراته يدوية عبر Play Console (§4.2) |

### 1.2 خريطة الماكينات الثلاث

| الماكينة | الوصول | دورها في المربي الذكي |
|---|---|---|
| **VPS** | `ssh root@72.62.44.131` | الإنتاج: `tg_backend` + nginx + كرونات الـVPS. نسخة git للإنتاج في `/root/tutor-guardian`. **تحذير:** على نفس الـVPS مواقع أخرى حية (analytics-platform وغيرها) — لا تلمسها |
| **لابتوب خالد** | (جهاز خالد الشخصي) | وكلاء المحتوى والتسويق عبر PCC (§5.2) + نسخة التطوير `/home/khalednew/projects/tutor-guardian` |
| **tg-home** | `ssh khaled@100.109.163.64` (Tailscale) | خادم Ollama للاستدلال المحلي |

تفاصيل الوصول الكاملة في `~/projects/ACCESS.md`. المفاتيح والصلاحيات تُطلب من خالد — لا تُنسخ ولا تُشارك.

---

## 2) سلسلة الاستدلال (LLM chain)

الترتيب داخل `backend/app/services/ai_gateway.py` (generate + stream):

1. **كاش الإجابات** (`answer_cache.py`): مطابقة دقيقة بعد تطبيع عربي، ثم تشابه دلالي (e5 cosine ≥ 0.92). يخدم أول سؤال في الجلسة فقط، إجابات محلية مؤصلة فقط، TTL 45 يومًا. كل إصابة تُسجَّل `provider=answer_cache` في `llm_calls`.
2. **Ollama المحلي على tg-home** (النموذج الأساسي ثم الاحتياطي `OLLAMA_FALLBACK_MODEL`).
3. **DeepSeek السحابي** — آخر حلقة فقط، بالسقف الشهري (fail-closed: لو تعذّر حساب الميزانية، الصمام يرفض).

قواعد ضبط التكلفة الفاعلة حاليًا:
- `AI_DAILY_LIMIT=20` طلب POST/جهاز/يوم (UTC) على نطاق الـAI فقط؛ الرفض بلطف مع Retry-After.
- القصص تُقدَّم من كاش مولّد مسبقًا بمفتاح (قيمة × عمر × جنس) بأبطال قانونيين (سالم/سارة) واستبدال الاسم وقت التقديم — أسماء الأطفال الحقيقية لا تُخزَّن أبدًا.

---

## 3) البيانات والتخزين

### 3.1 قواعد SQLite — اثنتان ولا تخلط بينهما

كلتاهما داخل volume `tg_sessions` المركّب على `/app/ops` في الحاوية:

| القاعدة | ماذا فيها | طبيعتها |
|---|---|---|
| `ops/sessions.db` | **تيليمتري التشغيل**: `llm_calls` (كل نداء LLM: المزوّد، التوكنز، الزمن — منها تُحسب p95 وميزانية الصمام ونسبة الكاش)، `answer_cache`، `retrieval_log`، `query_rewrites` | قابلة لإعادة البناء نظريًا؛ لكنها مصدر مقاييس التكلفة — لا تمسحها |
| `ops/conversations.db` | **بيانات المنتج والمستخدمين**: `chat_sessions/chat_messages`، `child_profiles`، `lesson_progress`، `habits_*`، `referrals`، `push_tokens`، `user_backups`… | **حرجة** — عليها الباكاب اليومي (§5.1) |

كل الاتصالات على WAL + `busy_timeout`. لا تفتح القاعدة الحية بأدوات كتابة من خارج الحاوية.

### 3.2 ⚠️ ChromaDB — خطر الترقية 0.x → 1.x

- الاعتماد مثبّت في `backend/requirements.txt`: `chromadb>=0.5,<1` مع تعليق صريح: **HOLD at <1**.
- الـvolume الإنتاجي `tg_chroma` مكتوب بصيغة **0.6**. رفع المكتبة لـ1.x يعني عدم قدرة الحاوية على قراءة الفهرس (هجرة صيغة بيانات).
- **لا ترفع البن أبدًا** ضمن تحديث dependencies روتيني. الترقية مشروع مستقل: خطة هجرة + إعادة بناء الفهرس (`ops/tools/build_vector_db.py`) + اختبار على نسخة من الـvolume + موافقة خالد.

### 3.3 الـvolumes والـmounts (من `docker-compose.production.yml`)

| المسار داخل الحاوية | المصدر | النوع |
|---|---|---|
| `/app/ops` | volume `tg_sessions` | بيانات حية (SQLite) |
| `/app/knowledge_base/chroma_db` | volume `tg_chroma` | فهرس RAG |
| `/app/ops/scripts` | bind من `/root/tutor-guardian/ops/scripts` | **قراءة فقط** — يظلّل ما داخل الصورة |
| `/app/docs` | bind من `/root/tutor-guardian/docs` | قراءة فقط — ميديا الدروس (~2GB، تُنقل rsync من اللابتوب، لا تُخبز في الصورة) |
| `/app/backend/secrets` | bind من `/root/tutor-guardian/backend/secrets` | قراءة فقط — مفتاح Firebase Admin (خارج الصورة ليسهل تدويره) |

**نتيجة عملية مهمة:** إصلاح سكربت في `ops/scripts/` (كرونات الدفع، pregen، الداشبورد…) يصل للإنتاج بـ`git pull` في `/root/tutor-guardian` فقط — **بدون rebuild ولا restart** (الكرونات تنفّذ السكربت من الـmount عند كل تشغيل). أما أي تعديل في `backend/` فيتطلب rebuild كامل (§4.1).

---

## 4) النشر (Deploy)

### 4.1 الباكند — الصورة مخبوزة، النشر = rebuild على الـVPS

المسار الطبيعي (مؤتمت): push إلى `main` → `deploy.yml` يعمل على **runner ذاتي الاستضافة داخل الـVPS نفسه** (لا SSH، ولا بوابة `workflow_run` — أُزيلت لتفادي فاتورة Actions). الوظيفة تبني صورة **مرشّحة** وتشغّل بداخلها pytest + فحص سلامة قاعدة المعرفة **قبل** لمس حاوية الإنتاج، فالسويت الحمراء لا تصل للإنتاج:

1. بناء `tutor-guardian-backend:candidate-<sha>` وتشغيل التستات بداخلها
2. `git fetch origin main && git reset --hard origin/main` في `/root/tutor-guardian`
3. `python3 ops/tools/check_served_assets.py` — يوقف النشر لو الفهرس يشير لملف غير موجود على الجهاز أو لبودكاست يتشاركه أكثر من درس
4. إعادة إنشاء الحاوية من الصورة المختبَرة (بلا بناء جديد)
5. انتظار `tg_backend` حتى `healthy` ثم فحص `/health` و`/privacy-policy` — وعند الفشل **رجوع تلقائي** لآخر صورة كانت سليمة

**تحذير:** كل push لـ`main` يمر بهذه البوابة = نشر فعلي على الإنتاج. لا تدمج في `main` ما لست مستعدًا لرؤيته live.

### البوابات — من يحرس ماذا

`Flutter` و`Backend tests` كانا `disabled_manually` من يونيو **لتفادي فاتورة Actions —
والفاتورة غير موجودة**: المستودع **عام**، وActions مجاني بلا حدود على المستودعات العامة
(`gh repo view --json visibility`). أُعيد تفعيلهما 2026-08-10 بعد تنظيف اللينت، وأول تشغيلة
بعدها خضراء. `Docker` يبقى مطفأً (مكرر مع بناء الصورة في النشر) و`CI` مُلغى عمدًا لصالح
`backend.yml`.

ثمن غيابهما كان ملموسًا: crash شاشة الكويز (قسمة 0/0 → `NaN.round()`) شُحن في ريليز
v1.0.30+75 دون أن يعترض شيء — لا لأن بوابة فشلت، بل لأنها لم تكن موجودة.

| الحارس | متى | ماذا يفحص |
|---|---|---|
| `.githooks/pre-commit` | كل commit | سلامة قاعدة المعرفة + `ruff` (٤ قواعد تمسك باج) |
| `.githooks/pre-push` | الدفعات التي تلمس `mobile/` فقط | `flutter analyze --fatal-infos --fatal-warnings` + `flutter test` |
| `Flutter` (CI) | دفعات `mobile/**` | نفس الفحصين على runner نظيف |
| `Backend tests` (CI) | دفعات الباكند/KB | pytest ×2 + سلامة قاعدة المعرفة + `ruff` |
| `deploy.yml` | كل نشر | pytest + سلامة KB داخل الصورة المرشّحة + `check_served_assets` (يوقف النشر) |

التداخل بين الهوكس والـCI متعمَّد: الهوك يردّ فورًا ويعمل بلا شبكة، والـCI يمسك ما تخطّاه
أحدهم بـ`--no-verify` أو دفعه من جهاز آخر. تحقق من الحالة: `gh workflow list --all`.

الـVPS لا يوجد به Flutter، لذا فحص الموبايل لا يمكن أن يعمل على الـrunner الذاتي.
التخطّي محليًا: `SKIP_MOBILE_CHECKS=1 git push` (غير محبّذ — الـCI سيمسكه على أي حال).

**فترة الإحماء:** بعد إقلاع الحاوية، تحميل الـembedders (ONNX) وفهرس Chroma يأخذ **~30–90 ثانية** (الـhealthcheck نفسه بـ`start_period: 90s`). خلالها `/seo` والـAPI يرجعان **502 من nginx — هذا طبيعي**، لا تتسرع بإعادة تشغيل ثانية. انتظر حتى `docker ps` يظهر `(healthy)`.

- إصلاح طارئ بدون CI: من GitHub → Actions → Deploy → Run workflow → `skip_ci=true` (للطوارئ فقط).
- rebuild يدوي على الـVPS يتبع نفس خطوات 1–4 أعلاه.

### 4.2 الموبايل — يدوي عبر Play Console

- البناء والرفع عبر Play Console **يدويًا** (حساب خالد). لا أتمتة نشر للموبايل.
- قبل أي إصدار: `flutter analyze` صفر أخطاء + كل تستات الـwidget خضراء + مراجعة Data Safety form (تطبيق فيه وضع طفل — سياسات Google Play Families).
- قائمة المتجر وأصول ASO في `docs/PLAY_STORE_LISTING.md`، وقائمة تدقيق الإصدار في `plans/release_checklist.md`.

### 4.3 المحتوى المعرفي

عند إضافة/تعديل وحدات معرفة: `python ops/tools/normalize_units.py` ثم `python ops/tools/build_vector_db.py` ثم `./check.sh --full`. حارس السلامة يعمل تلقائيًا في pre-commit والـCI.

---

## 5) المهام المجدولة

### 5.1 كرونات الـVPS (crontab الـroot — كلها UTC)

| الوقت | المهمة | اللوج | التحقق بالأثر |
|---|---|---|---|
| `0 2 * * *` | `docker-cleanup.sh` (تنظيف صور Docker) | `/var/log/docker-cleanup.log` | مساحة القرص لا تتضخم |
| `17 3 * * *` | `certbot renew` + إعادة تحميل nginx | لوجات certbot | تاريخ انتهاء الشهادة على الدومين |
| `0 17 * * *` | `cron_push_triggers.py` داخل الحاوية — إشعارات FCM (إعادة تفاعل المساء ≈8 مساءً فقط؛ **حد أقصى 1/جهاز/يوم**، ولا يتكرر للجهاز خلال 3 أيام — `--cap-days`) | `/var/log/tg-push.log` | إشعار وصل فعليًا لجهاز اختبار الساعة 17 UTC، **ولا شيء الساعة 07 صباح اليوم التالي** |
| `30 2 * * *` | `pregen_stories.py --max 20` — التوليد الليلي المسبق للقصص | `/var/log/tg-story-pregen.log` | صفوف جديدة في كاش القصص |
| `0 3 * * *` | `warm_answer_cache.py` — تسخين كاش الإجابات بأسئلة الألم الشائعة | `/var/log/tg-cache-warm.log` | نسبة الكاش في `/api/stats/ops-llm` |
| `30 3 * * *` | `backup_user_data.sh` — باكاب `conversations.db` (sqlite3 online backup + integrity_check، gzip، احتفاظ 14 يومًا) → `/root/tg-backups/` | `/var/log/tg-backup.log` | ملف اليوم موجود **وحجمه منطقي** واسترجاع تجريبي يفتح |
| أسبوعيًا `8:00` | `weekly_dashboard.py` — تقرير أسبوعي على تلجرام (مقاييس LLM + retention + إحصائيات DB) | `/var/log/tg-weekly-dashboard.log` | الرسالة وصلت فعلًا على تلجرام |
| (systemd timer) | `pcc-laptop-watchdog` — يراقب نبض لابتوب خالد وينبّه على تلجرام لو غاب > ساعتين (كود المؤقّت في `publishing-center/scripts/watchdog/`) | journalctl للـtimer | تنبيه فعلي عند إطفاء اللابتوب |

> درس مسجَّل (2026-07-16): سطر كرون قديم كان يشير لملف غير موجود، فظلت إشعارات إعادة التفاعل معطلة **صامتة** منذ الإعداد. لهذا: أي كرون جديد يُتحقق منه بالأثر (رسالة وصلت/صف اتكتب) لا بمجرد وجوده في crontab.

### 5.2 وكلاء PCC على اللابتوب (محتوى وتسويق — لا يمسّون الإنتاج)

تُدار حصريًا عبر PCC (المانيفست `publishing-center/manifest/agents.json` والداشبورد `http://127.0.0.1:8377`). لوجاتها في `~/.local/state/pcc/logs/<agent>/`. الحالة الحية: `pcc list`.

| الوكيل | جدوله وقت الكتابة | وظيفته |
|---|---|---|
| `tutor_post` | يوميًا 12:00 | نشر tip يومي (Buffer 3 حسابات + قناة تلجرام المربي) |
| `tutor_reels` | يوميًا 11:00 | توليد 3 ريلز تسويقية من البودكاستات الجاهزة |
| `tutor_podcasts` | كل ساعة (:15) | توليد بودكاستات الدروس المتبقية — يتقاعد ذاتيًا عند الانتهاء |
| `tutor_genvideos` | كل ساعتين (:45) | فيديوهات المسارات — **معطَّل 2026-07-15** (المهمة اكتملت) |

هذه الوكلاء منفصلة تمامًا عن خدمة الإنتاج: سقوطها يؤثر على التسويق فقط، لا على المستخدمين.

---

## 6) المراقبة

### 6.1 OMAR — المراقب العام

- يعمل من اللابتوب كل 30 دقيقة (`pcc run omar_monitor`) ويبعت تقريرًا على تلجرام لخالد.
- فحصا المربي الذكي:
  - **tutor-guardian**: `GET https://tg-api.alsaba.cloud/health` يتوقع `ok` (مهلة سماح 10 دقائق).
  - **tutor-guardian-llm**: `GET /api/stats/ops-llm` — p95 + توكنز/مزود شهريًا + نسبة الكاش + ميزانية صمام DeepSeek. يعلن degraded لو p95 > 30s أو استهلاك الصمام ≥ 80%.
- التنبيه صاخب عند الفشل 1 و3 ثم كل ~6 ساعات، مع إشعار «تعافى» عند الرجوع.
- لو اللابتوب نايم، OMAR يتوقف — وهنا يلتقط watchdog الـVPS الغياب وينبّه خلال ساعتين.

### 6.2 مقاييس التشغيل يدويًا

`GET https://tg-api.alsaba.cloud/api/stats/ops-llm` مع هيدر `X-Ops-Token` (قيمته سرّ — تُطلب من خالد، موجودة في `.env` الإنتاج وفي `~/.omar/.env` على اللابتوب). يعيد: p95 للاستجابة، توكنز لكل مزود شهريًا، توكنز/جهاز نشط، نسبة إصابات الكاش، نسبة استهلاك ميزانية صمام DeepSeek.

### 6.4 حلقة آراء المستخدمين ← تلجرام (ثنائية الاتجاه)

**ما تفعله:** أي رأي يُرسَل من التطبيق يصل خالد على تلجرام فورًا (نص + المذكرة الصوتية مرفوعة قابلة للتشغيل داخل الشات). والردّ على تلك الرسالة **من تلجرام** يصل للمستخدم داخل التطبيق (إشعار push + يظهر أعلى شاشة «شاركنا رأيك»).

**التفعيل — خطوات خالد (لمرة واحدة):**

1. أنشئ بوتًا **مخصّصًا** عبر `@BotFather`. ⚠️ **لا** تُعِد استخدام `TELEGRAM_BOT_TOKEN` التسويقي — البوت الواحد يحمل webhook واحدًا فقط.
2. راسل البوت برسالة أي، ثم افتح `https://api.telegram.org/bot<TOKEN>/getUpdates` لأخذ `chat.id`.
3. أضف للـ`.env` بجذر المشروع (صلاحية 600):
   ```
   FEEDBACK_TELEGRAM_BOT_TOKEN=...
   FEEDBACK_TELEGRAM_CHAT_ID=...
   FEEDBACK_TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)
   ```
4. أعد تشغيل الحاوية (تُحقن عبر `env_file:`)، ثم سجّل الـwebhook:
   ```
   python3 ops/scripts/set_feedback_webhook.py
   python3 ops/scripts/set_feedback_webhook.py --status
   ```
5. **سجّل القيد** في `publishing-center/OPERATIONS_LOG.md`.

**التحقق بالأثر الفعلي (لا exit 0):** أرسل رأيًا من التطبيق → لازم رسالة تصل تلجرام → رُدّ عليها → لازم الرد يظهر داخل التطبيق على نفس الجهاز.

**الأمان:** المسار `POST /api/feedback/telegram/webhook` عام في الـauth middleware (تلجرام بلا توكن جهاز) لكنه محروس بثلاثة حواجز: سرّ في هيدر `X-Telegram-Bot-Api-Secret-Token` يُقارن بزمن ثابت، وقائمة سماح على `chat_id`، وسقف حجم الجسم. **يفشل مغلقًا** — ما دام السرّ غير مضبوط يرفض كل شيء (403).

**لو التنبيهات ما وصلتش:** المتغيران غير مضبوطين → الكود يتخطّى الإرسال بصمت والرأي **يُخزَّن على أي حال**. راجع لوج الحاوية بحثًا عن `telegram sendMessage` / `telegram notify failed`.

**لو الردود ما وصلتش المستخدم:** الرد يُخزَّن أولًا ثم يُدفع؛ الدفع قد يفشل (توكن منتهٍ/إشعارات مغلقة). التطبيق يستطلع `GET /api/feedback/replies` عند كل فتح، فالوصول لا يعتمد على FCM. والفيدباك القديم بلا `device_id` لا يمكن الرد عليه إطلاقًا (يُسجَّل في اللوج).

**حدود:** `POST /api/feedback/app` بسقف 5 طلبات/دقيقة لكل IP (`RATE_LIMIT_FEEDBACK_PER_MINUTE`) — عام وبلا مصادقة ويقبل صوتًا 8MB.

### 6.3 القاعدة الذهبية: healthy ≠ exit 0

أي تحقق يكون **بالأثر الفعلي**، لا بنجاح الأمر:
- إشعارات؟ → إشعار وصل فعلًا لجهاز.
- باكاب؟ → الملف موجود بحجم منطقي **ويُسترجع** ويطابق القاعدة الحية.
- deploy؟ → الحاوية `healthy` + `/health` يرجع 200 **+ سؤال حقيقي للمحادثة يرجع إجابة**.
- كرون؟ → الصف/الملف/الرسالة الناتجة موجودة، لا مجرد سطر في crontab.

---

## 7) دليل الحوادث (Incident Playbook)

### 7.1 الباكند واقع (tg-api لا يرد / OMAR ينبه)

على الـVPS:
```bash
docker ps --filter name=tg_backend          # الحالة: up? healthy? starting?
docker logs --tail 200 tg_backend           # آخر الأخطاء
curl -s http://localhost:8000/health         # من غير المرور بـnginx؟ لأ — الحاوية بلا منفذ مكشوف؛ افحص عبر:
docker exec tg_backend curl -fsS http://localhost:8000/health
```
- الحالة `(health: starting)` أو 502 خلال أول ~90 ثانية بعد الإقلاع = **إحماء طبيعي** (§4.1). انتظر.
- الحاوية في restart loop → اقرأ اللوج؛ الأسباب الشائعة: متغير `.env` ناقص (الكود fail-closed مثلًا على `CHILD_MODE_SECRET`)، أو volume معطوب.
- إعادة تشغيل نظيفة: `docker compose -f docker-compose.production.yml restart backend` من `/root/tutor-guardian`.
- لو المشكلة من commit جديد: ارجع لآخر commit سليم في `/root/tutor-guardian` وأعد البناء، وسجّل الحادثة (§10).

### 7.2 سلسلة الـLLM متدهورة (المحادثة بطيئة/ساقطة، p95 عالي)

1. افحص `/api/stats/ops-llm`: من أي مزود تأتي النداءات الآن؟
2. لو النداءات تحولت لـ`deepseek_fallback` → السلسلة المحلية ساقطة: tg-home نايم؟ Tailscale واقع؟ Ollama متوقف؟
   - على tg-home: `systemctl status` لخدمة Ollama / `curl http://localhost:11434/api/tags`، و`tailscale status` على الطرفين.
3. الصمام السحابي يحمي الخدمة مؤقتًا لكن **بميزانية محدودة**: عند اقتراب الاستهلاك من السقف (OMAR ينبه عند 80%) أعِد المحلي للعمل فورًا — عند نفاد السقف تسقط المحادثة كليًا (fail-closed مقصود).
4. p95 عالي مع بقاء المزود المحلي = ضغط على tg-home (نموذج أثقل؟ حمل موازٍ؟) — افحص موارد tg-home.

### 7.3 قرص/ذاكرة

- الـVPS مشترك مع خدمات أخرى؛ حاوية الباكند محدودة بـ2 CPU / 4GB (compose). `docker stats tg_backend` للاستهلاك اللحظي.
- القرص: `df -h` — أكبر المشتبه بهم: صور Docker القديمة (`docker system df`؛ التنظيف اليومي 2:00 موجود أصلًا)، لوجات `/var/log/tg-*.log`، وباكابات `/root/tg-backups/` (الاحتفاظ 14 يومًا تلقائي).
- **ممنوع الحذف اليدوي لبيانات المستخدمين أو الـvolumes نهائيًا.**

### 7.4 أين اللوجات؟

| ماذا | أين |
|---|---|
| كرونات المربي على الـVPS | `/var/log/tg-*.log` |
| الباكند نفسه | `docker logs tg_backend` |
| وكلاء PCC على اللابتوب | `~/.local/state/pcc/logs/<agent>/` |
| نبض OMAR | `~/.omar/heartbeats.json` على اللابتوب |
| تاريخ القرارات التشغيلية | `publishing-center/OPERATIONS_LOG.md` |

---

## 8) الباكاب والاسترجاع

- باكاب يومي 3:30 UTC لـ`conversations.db` عبر sqlite3 online backup (آمن مع WAL) + `integrity_check` + gzip → `/root/tg-backups/`، احتفاظ 14 يومًا.
- **اختبار الاسترجاع دوريًا** (شهريًا على الأقل): فك أحدث ملف، افتحه بsqlite3، قارن عدد صفوف جدول مرجعي (مثل `chat_sessions`) مع القاعدة الحية.
- المستخدمون لديهم أيضًا مزامنة مشفّرة Zero-Knowledge (`user_backups`) — الخادم لا يستطيع قراءة محتواها، فهي ليست بديلًا عن الباكاب التشغيلي.

---

## 9) سياسة الأسرار — اقرأها مرتين

1. **كل الأسرار تعيش في ملفات `.env` بصلاحية 600** على الماكينة المعنية فقط (الإنتاج: `/root/tutor-guardian/.env` — التطوير: `.env` محلي — OMAR: `~/.omar/.env`). مفتاح Firebase Admin ملف منفصل bind-mounted بصلاحية 600.
2. **ممنوع منعًا باتًا**: سر في كود، في commit، في سطر أمر (ولا حتى `echo`/`printf`)، في لوج، في هذا الدليل، في تذكرة، في سكرينشوت.
3. أسرار PCC المركزية تُدار بـ`pcc set-secret` فقط.
4. عند تدوير سر: حدّث `.env` → أعد تشغيل/بناء الحاوية → **تحقق بالأثر** (نداء حقيقي ينجح بالسر الجديد) → سجّل التدوير في OPERATIONS_LOG (دون القيمة طبعًا).
5. **أسماء** المتغيرات المهمة (القيم عند خالد فقط — اطلب الحد الأدنى الذي تحتاجه لمهمتك):

| الاسم | وظيفته |
|---|---|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` / `TELEGRAM_CHANNEL_ID` | تقارير تلجرام (الداشبورد الأسبوعي/OMAR/النشر) |
| `OPS_METRICS_TOKEN` | حماية `/api/stats/ops-llm` على الباكند |
| `TG_OPS_METRICS_TOKEN` | نفس التوكن من جهة OMAR (`~/.omar/.env`) |
| `DEEPSEEK_API_KEY` + `DEEPSEEK_FALLBACK_ENABLED` + `DEEPSEEK_FALLBACK_MONTHLY_TOKEN_CAP` | صمام الأمان السحابي وسقفه |
| `CHILD_MODE_SECRET` | توقيع وضع الطفل — الكود يرفض الإقلاع بدونه |
| `FEEDBACK_ADMIN_KEY` | واجهة مراجعة الملاحظات |
| `BUFFER_ACCESS_TOKEN` | نشر تسويقي (وكيل `tutor_post`) |
| `OLLAMA_BASE_URL` وأخواتها | عنوان الاستدلال المحلي (Tailscale) وإعداداته |
| `AI_DAILY_LIMIT` / `COACH_TIP_ENABLED` | ليست أسرارًا لكنها مفاتيح تشغيل حساسة — لا تغيّرها دون تسجيل |
| `backend/secrets/firebase-adminsdk.json` | مفتاح Firebase Admin (إشعارات FCM) — ملف، ليس متغيرًا |

**من يعطيك الوصول؟ خالد فقط** (khalidhamdy50@gmail.com). لا يوجد مسار آخر شرعي للحصول على سر.

---

## 10) انضباط التغيير

1. **كل تغيير تشغيلي** (إيقاف/تفعيل وكيل، تعديل كرون، تغيير على السيرفرات، تدوير سر، deploy يدوي، أي حادثة وحلها) **يُسجَّل فورًا** بقيد مؤرَّخ في `~/projects/publishing-center/OPERATIONS_LOG.md` + commit. القيد يتضمن: ماذا، لماذا، وكيف تحققت بالأثر.
2. **crontab اللابتوب مُدار من PCC حصريًا** (البلوك بين BEGIN/END PCC MANAGED). ممنوع تعديله يدويًا — أي جدولة جديدة: أضِفها في `publishing-center/manifest/agents.json` ثم `pcc sync && pcc cron-sync`. تعطيل وكيل: `pcc disable <id> --reason "..."` (السبب إجباري).
3. كرونات الـVPS تُعدَّل يدويًا هناك، لكن **يجب** تحديث `~/projects/CRONS.md` وتسجيل القيد في OPERATIONS_LOG في نفس الجلسة.
4. قبل نقل/مسح أي ملف: تأكد أن لا خدمة ولا كرون ولا مانيفست PCC يشير إليه، وبعد النقل تأكد أن الخدمات لسه شغالة. القديم يُنقل لـ`_archive/` — لا يُمسح.
5. تعديلات الكود تمر عبر PR/CI الطبيعي؛ تذكّر أن merge لـ`main` = deploy (§4.1).

---

## 11) مراجع سريعة

| الملف | ماذا فيه |
|---|---|
| `plans/growth-master-plan-2026-07.md` | الخطة الرئيسية (الدستور، المراحل، KPIs) |
| `~/projects/CLAUDE.md` | قواعد المنظومة كلها (اقرأه قبل أي شيء) |
| `~/projects/CRONS.md` | المرجع الحي لكل الجدولة |
| `~/projects/ACCESS.md` | دليل الوصول للماكينات |
| `publishing-center/OPERATIONS_LOG.md` | تاريخ كل قرار تشغيلي |
| `README.md` + `API.md` + `MOBILE_API.md` | تشغيل التطوير المحلي وعقد الـAPI |
| `docs/PLAY_STORE_LISTING.md` | حزمة ASO ونِسخ المتجر |
| `plans/release_checklist.md` | قائمة تدقيق إصدارات الموبايل |
