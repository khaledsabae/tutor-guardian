# دليل النموذج وتوليد بيانات التدريب (Fine-Tuning)

> مرجع لأي وكيل/مطوّر: كيف يعمل النموذج المحلي، كيف نولّد بيانات التدريب، كيف نفحص
> جودتها، وكيف ندرّب نسخة مخصّصة (`tg-tutor`) ونرجّعها للسيرفر.

---

## 1. السيرفر المحلي (Ollama)

النموذج يعمل **محلياً 100%** على جهاز منزلي (HP EliteBook، i7-1165G7، 32GB RAM، **بدون GPU**)،
ويُوصَل عبر **Tailscale**:

```
Base URL : http://100.109.163.64:11434
SSH      : ssh -i ~/.ssh/id_ed25519 khaled@100.109.163.64
```

النماذج المتاحة:
| النموذج | الدور | السرعة (CPU) |
|---------|-------|--------------|
| `qwen2.5:3b` | classifier + ردّ سريع | ~14-16 tok/s |
| `gemma4:e4b` | جودة أعلى | ~9 tok/s |
| `gemma4:e4b-it-qat` | توليد بيانات التدريب (QAT، جودة عربية أعلى) | ~9 tok/s |

اختبار سريع للسيرفر:
```bash
curl http://100.109.163.64:11434/api/tags      # قائمة النماذج
curl http://100.109.163.64:11434/api/generate -d '{"model":"gemma4:e4b-it-qat","prompt":"مرحبا","stream":false}'
```

---

## 2. توليد بيانات التدريب (Q&A dataset)

السكربت: `ops/tools/generate_qa_dataset.py` — يقرأ الـ292 وحدة معرفية ويولّد 3 أسئلة/إجابات لكل وحدة.

```bash
nohup backend/.venv/bin/python3 ops/tools/generate_qa_dataset.py \
  --model gemma4:e4b-it-qat \
  --ollama-url http://100.109.163.64:11434 \
  --questions-per-unit 3 \
  --output ops/data/qa_dataset.jsonl \
  --checkpoint ops/data/qa_checkpoint.json \
  > ops/data/qa_gen.log 2>&1 &
echo $! > ops/data/qa_gen.pid
```

> **⚠️ بطيء بطبيعته:** على CPU بدون GPU، كل وحدة ~7-8 دقائق (3 توليدات كاملة) → الـ292 وحدة
> تأخذ **~36-40 ساعة**. هذا **طبيعي** وليس عطلاً. الـ `--checkpoint` يسمح بالاستئناف لو توقّف.

### مراقبة التقدّم
```bash
wc -l ops/data/qa_dataset.jsonl                       # عدد الأزواج المولّدة
tail -3 ops/data/qa_gen.log                           # آخر وحدة + الزمن
kill -0 $(cat ops/data/qa_gen.pid) && echo "شغّالة" || echo "وقفت"
```

### إعادة التشغيل لو توقّف
نفس الأمر أعلاه — الـ checkpoint يتخطّى الوحدات المُنجزة تلقائياً.

> الناتج (`ops/data/qa_*.jsonl/.log/.pid/checkpoint`) **مُتجاهَل في git** (مُولّد محلياً، يُرفع لـ Kaggle منفصلاً).

---

## 3. فحص جودة الناتج

كل صف JSONL: `{instruction, output, domain, age_group, behavior_type, reference, unit_id}`.

سكربت فحص سريع (كان آخر تشغيل: **848 زوج، 0 مشاكل**):
```bash
python3 - <<'EOF'
import json, re
from collections import Counter
rows=[json.loads(l) for l in open("ops/data/qa_dataset.jsonl",encoding="utf-8") if l.strip()]
print("أزواج:", len(rows))
print("دومين:", dict(Counter(r['domain'] for r in rows)))
leak=re.compile(r'(As an AI|بصفتي نموذج|You are|instruction:|output:)',re.I)
p={'فاضي':0,'قصير':0,'تسريب':0,'إنجليزي':0}
for r in rows:
    o=r.get('output','').strip()
    if not o: p['فاضي']+=1
    elif len(o)<40: p['قصير']+=1
    if leak.search(o): p['تسريب']+=1
    body=o.split('📚')[0]
    lat=len(re.findall(r'[A-Za-z]',body)); ar=len(re.findall(r'[؀-ۿ]',body))
    if ar and lat>ar*0.5: p['إنجليزي']+=1
print("مشاكل:", p)   # كلها لازم تكون 0
EOF
```

معاينة عيّنات:
```bash
head -1 ops/data/qa_dataset.jsonl | python3 -m json.tool --no-ensure-ascii
```

---

## 4. التدريب (Fine-Tuning) على Kaggle

النوتبوك: `ops/kaggle/finetune_tg_kaggle.ipynb` (Unsloth + QLoRA، يصدّر GGUF Q4_K_M).
(بديل: `ops/colab/finetune_tg.ipynb`.)

الخطوات:
1. ارفع `ops/data/qa_dataset.jsonl` كـ **Kaggle Dataset** باسم `tg-qa-dataset`.
2. افتح النوتبوك: `kaggle.com/code/khaledsabae/tutor-guardian-arabic-parenting-llm-fine-tune`.
3. أضِف الـ dataset من **+ Add Data**.
4. فعّل **T4 GPU + Internet** من Settings.
5. **Run All** → ينتهي خلال ~2-3 ساعات.
6. نزّل من الـ Output: `tg-tutor-v1-Q4_K_M.gguf` + `Modelfile.tg-tutor`.

> ⚠️ **أمان:** Kaggle API token يُجدَّد من `kaggle.com/settings` بعد التدريب
> (التوكن القديم اتشارك في محادثات — لازم يتغيّر).

---

## 5. نشر النموذج المدرَّب على السيرفر المحلي

```bash
# على السيرفر المنزلي (Tailscale)
scp tg-tutor-v1-Q4_K_M.gguf Modelfile.tg-tutor khaled@100.109.163.64:~/
ssh khaled@100.109.163.64 'ollama create tg-tutor:v2 -f ~/Modelfile.tg-tutor'
```

ثم على الـ VPS، حدّث متغيّر البيئة:
```
OLLAMA_PRIMARY_MODEL=tg-tutor:v2
```
وأعد تشغيل الـ backend container. الـ AI gateway سيستخدم النموذج المخصّص تلقائياً.

---

## 6. ملخص المسارات

```
292 وحدة (knowledge_base/units/)
   └─ generate_qa_dataset.py  →  ops/data/qa_dataset.jsonl  (~848 زوج، gitignored)
        └─ Kaggle (Unsloth QLoRA)  →  tg-tutor-v1-Q4_K_M.gguf
             └─ ollama create tg-tutor:v2  →  السيرفر المحلي
                  └─ OLLAMA_PRIMARY_MODEL على الـ VPS
```
