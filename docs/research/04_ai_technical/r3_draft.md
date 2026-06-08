# AI Architecture & Local Inference Blueprint: Tutor Guardian

## 1. Local Arabic Model Benchmarks (8-16GB RAM Constraints)

### 1.1 Comparative Model Matrix

> ملاحظة مهمة: كل القيم الزمنية والأداء في الجدول أدناه هي [استدلال] مبنية على مواصفات النماذج ونتائج منشورة عامة (مثل جداول الأداء وقياسات السرعة)، وليست قياسات مخبرية على عتاد Tutor Guardian نفسه؛ هذا سلوك متوقع، وليس مضموناً. [gpustack](https://gpustack.ai/running-full-qwen-2-5-series/)

| Model Spec        | Size / Quantization                                                                 | Arabic NLP Score (Parenting/Islamic)                                                                                                                                                                      | Inference Speed (Tokens/s @ 12GB RAM)                                                                                             | VRAM Footprint (Model + KV Cache)                             |
|------------------|--------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| Qwen 2.5 (3B)    | ~3.1B params, INT4 `Q4_K_M` via Ollama (`qwen2.5-3b:q4_k_m`-class) [huggingface](https://huggingface.co/Qwen/Qwen2.5-3B)    | [استدلال] قوي متوقَّع في العربية العامة بسبب التدريب متعدد اللغات حتى 18T token، يُعتمد كنموذج عربي رئيسي لتربية إسلامية، مع ضرورة بناء مجموعة تقييم داخلية متخصصة؛ هذا سلوك متوقع، وليس مضموناً. [gpustack](https://gpustack.ai/running-full-qwen-2-5-series/) | [استدلال] تقريباً 15–30 tok/s على GPU متوسط (RTX 3060–4070) و4–8 tok/s على CPU لنسخة INT4، مع انخفاض تدريجي مع طول السياق؛ هذا سلوك متوقع، وليس مضموناً. [gpustack](https://gpustack.ai/running-full-qwen-2-5-series/) | [استدلال] ~3–4 GB على GPU (INT4 + كاش)، و~3 GB RAM على CPU وفق توصيات q4_k_m؛ هذا سلوك متوقع، وليس مضموناً. [ollama](https://ollama.com/novaforgeai/qwen2.5-3b:q4km)  |
| Phi-4 (Mini)     | 3.8B params, INT4 (`phi-4-mini-instruct`-class) [pub.towardsai](https://pub.towardsai.net/phi-4-multimodal-phi-4-mini-747852fd2688)               | [استدلال] أداء عربي جيد متوقَّع مع تفوق واضح في المنطق والرياضيات مقارنة بنماذج بحجم مشابه، مما يجعله نموذجاً مكمِّلاً عندما تكون المسائل المنطقية/التربوية المعقدة بارزة؛ هذا سلوك متوقع، وليس مضموناً. [pub.towardsai](https://pub.towardsai.net/phi-4-multimodal-phi-4-mini-747852fd2688) | [استدلال] 10–25 tok/s على GPU متوسط في INT4 بسبب زيادة المعاملات (3.8B) لكنه ما يزال مناسباً للعمل التفاعلي؛ هذا سلوك متوقع، وليس مضموناً.                        | [استدلال] ~4–5 GB على GPU في INT4 مع سياق 4K–8K عملي؛ هذا سلوك متوقع، وليس مضموناً.                    |
| Gemma Fallback   | [استدلال] Gemma 4 Small (≈4–5B params), INT4 QAT-quantized [deepmind](https://deepmind.google/models/gemma/gemma-3/)    | [استدلال] دعم عربي جيّد متوقَّع، مع قوة خاصة في الاستدلال متعدد اللغات، يُستخدم كخيار احتياطي عند الحاجة لتوافق أعلى مع بيئات Google/Android أو نمط استدلال مختلف؛ هذا سلوك متوقع، وليس مضموناً.     | [استدلال] 10–20 tok/s تقريباً على GPU 12GB في INT4، أبطأ قليلاً من Qwen 2.5 (3B) بسبب الحجم الأكبر؛ هذا سلوك متوقع، وليس مضموناً.                               | [استدلال] ~5–6 GB على GPU في INT4، مع إمكانية التشغيل على بطاقة واحدة مع QAT كما في تقارير Gemma 3؛ هذا سلوك متوقع، وليس مضموناً. [deepmind](https://deepmind.google/models/gemma/gemma-3/) |

> لا توجد معلومات موثوقة منشورة حول “Arabic NLP Score (Parenting/Islamic)” كنقاط معيارية جاهزة؛ القيم في هذا العمود هي أوصاف نسبية [استدلال] تعتمد على طبيعة البيانات والتقارير العامة لكل نموذج، وليست نتائج Benchmark رسمية على مجموعة بيانات تربية إسلامية متخصصة. [pub.towardsai](https://pub.towardsai.net/phi-4-multimodal-phi-4-mini-747852fd2688)

### 1.2 Quantitative Assessment & Quantization Choice

**1) اختيار النموذج الأساسي (Primary Arabic Tutor Model)**  
[استدلال] بالنظر إلى أن Qwen 2.5 متوفر بأحجام متعددة، مع نسخة 3B تدعم سياق حتى 32K وتركيز على تحسين اتباع التعليمات والاستجابات الطويلة، فإن اختيار حجم 3B بنسخة INT4 (`Q4_K_M`) يعطي توازناً مناسباً بين جودة العربية، الاستدلال، وسرعة التنفيذ في حدود 8–16GB RAM؛ هذا سلوك متوقع، وليس مضموناً. [ollama](https://ollama.com/novaforgeai/qwen2.5-3b:q4km)

- **أسباب الاختيار التقنية:**
  - حجم 3B يعطي مساحة كافية لتمثيل البنى النحوية العربية دون التضحية الكبيرة بالسرعة مقارنة بـ 7B. [gpustack](https://gpustack.ai/running-full-qwen-2-5-series/)
  - نسخة Q4_K_M موصى بها للإنتاج في مجتمع Ollama كنقطة توازن بين الدقة والسرعة والاستقرار، مع استهلاك RAM ~3 GB على أنظمة منخفضة الموارد. [ollama](https://ollama.com/novaforgeai/qwen2.5-3b:q4km)
  - INT4 يقلل الذاكرة بشكل كبير مع تدهور محدود في الجودة مقارنة بـ INT8 أو FP16، خصوصاً مع نماذج حديثة أُخذ فيها التكميم بالحسبان أثناء التصميم. [gpustack](https://gpustack.ai/running-full-qwen-2-5-series/)

**2) استراتيجية التكميم (INT4 vs INT8) تحت قيود 8–16GB**

- [استدلال] على عتاد 8GB RAM/VRAM:
  - يُفضَّل استخدام Qwen 2.5 (3B) بتكميم INT4 `Q4_K_M` وسياق عملي 4K–8K tokens، مما يسمح بتشغيل النموذج على أجهزة محمولة أو سيرفر منزلي بدون Swap كثيف؛ هذا سلوك متوقع، وليس مضموناً. [ollama](https://ollama.com/novaforgeai/qwen2.5-3b:q4km)
  - يمكن خفض السياق إلى 2K في سيناريوهات الأجهزة الأضعف أو عند وجود عدة مستخدمين متزامنين. [ollama](https://ollama.com/novaforgeai/qwen2.5-3b:q4km)
- [استدلال] على عتاد 12–16GB RAM/VRAM:
  - يمكن الاحتفاظ بـ Qwen 2.5 (3B) INT4 كنموذج افتراضي، مع رفع السياق إلى 8K–16K tokens.
  - تشغيل Phi-4 Mini (3.8B) أو Gemma Small INT4 كنماذج مكمِّلة (Co-pilot) لمسائل المنطق المعقدة أو مراجعة الإجابات الحساسة، ضمن حدود الذاكرة نفسها؛ هذا سلوك متوقع، وليس مضموناً. [ai.azure](https://ai.azure.com/catalog/models/Phi-4-mini-instruct)

**3) منهجية قياس الأداء (مقترحة للتنفيذ داخل Tutor Guardian)**  
لا توجد معلومات موثوقة جاهزة لقياسات TPS/TTFT على نفس مواصفات عتاد Tutor Guardian، لكن يمكن اعتماد خطة الاختبار التالية داخلياً، مع تصنيف النتائج كبيانات متحققة لاحقاً:

- **مقاييس زمنية:**
  - TTFT: الزمن من إرسال الطلب إلى ظهور أول token.
  - TPS: معدل التوليد بعد أول token.
- **سيناريوهات اختبار عربية متخصصة:**
  - أسئلة تربية إسلامية (حدود، طاعة الوالدين، استخدام الأجهزة، ...).
  - مواقف حوارية بين الوالد والطفل تتضمن مشاعر وغضب وحدود شرعية.
- **آلية تقييم الجودة:**
  - مراجعة بشرية من مختصين شرعيين وتربويين لمجموعة ثابتة (مثلاً 200–300 سؤال/حالة).
  - ترميز النتائج لمقاييس مثل: مدى الالتزام بالأحكام، وضوح اللغة، عدم إصدار فتاوى خارج نطاق المنهج المعتمد.

> إلى أن تُنفَّذ هذه الاختبارات، تظل جميع مقارنات جودة العربية في هذا الملف ضمن فئة [استدلال]، وليست حقائق قياسية نهائية؛ هذا سلوك متوقع، وليس مضموناً.

***

## 2. Optimized Arabic RAG Subsystem

### 2.1 Tokenization & Semantic Chunking Strategy

#### Arabic Text Normalization Pipeline

> العناصر أدناه تمثل أفضل ممارسة [استدلال] مستخلصة من أدبيات RAG متعددة اللغات وتقارير BGE‑M3، مع تكييف خاص للعربية؛ هذا سلوك متوقع، وليس مضموناً. [milvus](https://milvus.io/docs/ar/embed-with-bgm-m3.md)

- **تطبيع التشكيل (Tashkeel):**
  - إزالة جميع العلامات (الفتحة، الضمة، الكسرة، السكون، الشدة، التنوين) لتقليل اختلافات السطح، مع الاحتفاظ بنسخة أصلية للعرض إن لزم.
- **توحيد الألف:**
  - تحويل (أ، إ، آ، ٱ) إلى "ا" لتقليل تشتت التوكنات: `أطفال` → `اطفال`.
- **توحيد الياء/الألف المقصورة:**
  - تحويل "ى" إلى "ي" في نهاية الكلمات: `على` تبقى لكن `هدى` → `هدي` بحسب سياسة الفريق؛ يمكن الاحتفاظ بقائمة استثناءات.[استدلال]
- **استبدال التاء المربوطة:**
  - تحويل "ة" إلى "ه" أو "ت" وفق سياق الكلمة؛ في التطبيق العملي، كثير من الأنظمة تُبقي "ة" كما هي وتكتفي بالتوحيد الجزئي لتجنب أخطاء دلالية.[استدلال]
- **إزالة الكشيدة (ـ) والرموز الزائدة:**
  - حذف الكشيدة وأي رموز زخرفية أو غير لغوية شائعة في الكتب/المنشورات.[استدلال]
- **تطبيع المسافات والترقيم:**
  - توحيد علامات الترقيم إلى مجموعة محددة (، . ؟ ! :) وتحويل الفواصل الغربية إلى عربية أو العكس حسب السياسة الموحدة.[استدلال]
- **التعامل مع اللواصق (Clitics):**
  - استخدام مقطِّع عربي يحافظ على الضمائر والواوات/الفاءات كتوكنات مستقلة عند الإمكان (`وبابك` → `و` + `باب` + `ك`) لتحسين استرجاع المعنى في RAG.[استدلال]

هذه الخطوات تساعد نماذج التضمين متعددة اللغات مثل BGE‑M3 على تمثيل النص العربي بشكل أكثر استقراراً عبر تنويعات الكتابة المختلفة. [bge-model](https://bge-model.com/bge/bge_m3.html)

#### Chunk Size & Overlap Metrics

دراسة حديثة حول تحسين RAG العربي تشير إلى أن تقسيم النصوص العربية على حدود الجمل يتفوق على التقسيم الثابت بالtokens من حيث جودة الاسترجاع. بناءً على ذلك: [arxiv](https://arxiv.org/html/2506.06339v1)

- **استراتيجية التقسيم (Chunking):**
  - [استدلال] استخدام تقطيع واعٍ للجمل (sentence-aware) مع اعتبار الفقرات التربوية/الشرعية كوحدة دلالية أساسية؛ هذا سلوك متوقع، وليس مضموناً. [arxiv](https://arxiv.org/html/2506.06339v1)
- **حجم الـ Chunk:**
  - [استدلال] 200–350 token عربي (بعد التطبيع)، أي تقريباً 900–1,600 حرف عربي، مناسب لتوازن “سياق كافٍ” مع “تخصص موضوعي” لمقاطع التربية الإسلامية؛ هذا سلوك متوقع، وليس مضموناً.
- **التداخل (Overlap):**
  - [استدلال] تداخل 15–25% بين الـ chunks (مثلاً 40–70 token) لتقليل قطع السياق بين حكمين متتالين أو مثال وشرحه؛ هذا سلوك متوقع، وليس مضموناً.
- **تقسيم هرمي (Hierarchical):**
  - طبقة أولى على مستوى “الموضوع التربوي” (مثل: استخدام الهاتف، الصلاة، العلاقات مع الإخوة).
  - طبقة ثانية على مستوى الفقرة/المسألة داخل الموضوع.
  - هذا يسمح بتصفية أولية بالموضوع ثم بـ embedding.[استدلال]

### 2.2 Local Retrieval Execution (FastAPI + Python Implementation)

الكود التالي يوضح مساراً عملياً من تحميل مستندات عربية، تطبيعها وتقسيمها، توليد تضمينات محلية، وبناء استرجاع مخصص عبر FastAPI باستخدام نموذج تضمين عربي-إنجليزي مبني على BGE‑M3. [huggingface](https://huggingface.co/sayed0am/arabic-english-bge-m3)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import sqlite3
import faiss
import numpy as np
import re

from sentence_transformers import SentenceTransformer  # uses local HF cache/models

# ---------------------------
# Config & Model Initialization
# ---------------------------

DB_PATH = "tutor_guardian.db"
EMBED_MODEL_NAME = "sayed0am/arabic-english-bge-m3"  # Arabic-optimized BGE-M3 variant[web:19]
TOP_K = 8

app = FastAPI(title="Tutor Guardian RAG API", version="1.0.0")

# Load embedding model once at startup (local, no external telemetry).
embed_model = SentenceTransformer(EMBED_MODEL_NAME)

# FAISS index will store dense vectors; metadata kept in SQLite.
dimension = embed_model.get_sentence_embedding_dimension()
faiss_index = faiss.IndexFlatIP(dimension)  # inner product (cosine after normalization)

# ---------------------------
# SQLite Helpers
# ---------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id TEXT UNIQUE,
            topic TEXT,
            age_group TEXT,
            domain TEXT,
            content TEXT
        )
        """
    )
    conn.commit()
    conn.close()

# ---------------------------
# Arabic Normalization & Chunking
# ---------------------------

ARABIC_DIACRITICS_RE = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u06D6-\u06ED]"
)  # tashkeel ranges

def normalize_arabic(text: str) -> str:
    # Remove diacritics
    text = ARABIC_DIACRITICS_RE.sub("", text)

    # Remove tatweel
    text = text.replace("ـ", "")

    # Normalize Alef variants to bare Alef
    text = re.sub(r"[إأآٱ]", "ا", text)

    # Normalize Yeh/Alef Maqsura
    text = text.replace("ى", "ي")

    # Normalize punctuation spacing
    text = re.sub(r"\s+", " ", text).strip()
    return text

def sentence_split(text: str) -> List[str]:
    # Very simple sentence splitter for Arabic; can be replaced by spaCy / PyArabic if available.
    sentences = re.split(r"(?<=[\.!\؟\!])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences

def chunk_arabic_text(
    text: str,
    max_tokens: int = 256,
    overlap_tokens: int = 48,
) -> List[str]:
    """
    Naive token-based chunking using whitespace as proxy for tokens.
    For production, replace with tokenizer-based counting compatible with the LLM.
    """
    normalized = normalize_arabic(text)
    sentences = sentence_split(normalized)

    chunks = []
    current_tokens = []
    current_len = 0

    for sent in sentences:
        tokens = sent.split()
        if current_len + len(tokens) <= max_tokens:
            current_tokens.extend(tokens)
            current_len += len(tokens)
        else:
            if current_tokens:
                chunks.append(" ".join(current_tokens))
            # Start new chunk with overlap
            overlap = current_tokens[-overlap_tokens:] if overlap_tokens < len(current_tokens) else current_tokens
            current_tokens = overlap + tokens
            current_len = len(current_tokens)

    if current_tokens:
        chunks.append(" ".join(current_tokens))

    return chunks

# ---------------------------
# Embedding & Index Helpers
# ---------------------------

def embed_texts(texts: List[str]) -> np.ndarray:
    embeddings = embed_model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    if not isinstance(embeddings, np.ndarray):
        embeddings = np.array(embeddings)
    return embeddings.astype("float32")

def build_faiss_index_from_db():
    global faiss_index
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT content FROM documents ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return

    docs = [row["content"] for row in rows]
    vectors = embed_texts(docs)
    faiss_index = faiss.IndexFlatIP(vectors.shape [gpustack](https://gpustack.ai/running-full-qwen-2-5-series/))
    faiss_index.add(vectors)

# ---------------------------
# Pydantic Models
# ---------------------------

class IngestDocument(BaseModel):
    topic: str
    age_group: str  # e.g. "6-8", "9-12"
    domain: str     # e.g. "screen_time", "prayer", "anger_management"
    text: str

class SearchRequest(BaseModel):
    query: str
    age_group: Optional[str] = None
    domain: Optional[str] = None
    top_k: int = TOP_K

class RetrievedChunk(BaseModel):
    content: str
    topic: str
    age_group: str
    domain: str
    score: float

class SearchResponse(BaseModel):
    query: str
    retrieved: List[RetrievedChunk]

# ---------------------------
# API Endpoints
# ---------------------------

@app.on_event("startup")
def startup_event():
    init_db()
    build_faiss_index_from_db()

@app.post("/ingest", status_code=201)
def ingest_document(doc: IngestDocument):
    chunks = chunk_arabic_text(doc.text)

    if not chunks:
        raise HTTPException(status_code=400, detail="Document is empty after normalization/chunking.")

    conn = get_db()
    cur = conn.cursor()

    for idx, chunk in enumerate(chunks):
        chunk_id = f"{doc.topic}:{doc.age_group}:{doc.domain}:{idx}"
        try:
            cur.execute(
                """
                INSERT INTO documents (chunk_id, topic, age_group, domain, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chunk_id, doc.topic, doc.age_group, doc.domain, chunk),
            )
        except sqlite3.IntegrityError:
            # If chunk_id already exists, skip; idempotent ingestion behavior.
            continue

    conn.commit()
    conn.close()

    # Rebuild FAISS index after ingestion (for large corpora, schedule offline build).
    build_faiss_index_from_db()

    return {"status": "ok", "chunks_ingested": len(chunks)}

@app.post("/search", response_model=SearchResponse)
def search_documents(req: SearchRequest):
    if faiss_index.ntotal == 0:
        raise HTTPException(status_code=503, detail="Index is empty. Ingest documents first.")

    # Step 1: DB filter by (age_group, domain) if provided
    db = get_db()
    cur = db.cursor()

    query_parts = ["1=1"]
    params: List[str] = []

    if req.age_group:
        query_parts.append("age_group = ?")
        params.append(req.age_group)

    if req.domain:
        query_parts.append("domain = ?")
        params.append(req.domain)

    where_clause = " AND ".join(query_parts)
    cur.execute(f"SELECT id, topic, age_group, domain, content FROM documents WHERE {where_clause} ORDER BY id ASC", params)
    rows = cur.fetchall()
    db.close()

    if not rows:
        return SearchResponse(query=req.query, retrieved=[])

    docs = [row["content"] for row in rows]
    meta = [(row["id"], row["topic"], row["age_group"], row["domain"]) for row in rows]

    # Step 2: Embed query & docs, run dense retrieval locally
    query_vec = embed_texts([normalize_arabic(req.query)])
    doc_vecs = embed_texts(docs)

    # For per-request filtered search, we can create a temporary FAISS index
    index = faiss.IndexFlatIP(doc_vecs.shape [gpustack](https://gpustack.ai/running-full-qwen-2-5-series/))
    index.add(doc_vecs)

    scores, indices = index.search(query_vec, min(req.top_k, len(docs)))

    retrieved_chunks: List[RetrievedChunk] = []
    for rank, idx in enumerate(indices[0]):
        if idx == -1:
            continue
        score = float(scores[0][rank])
        doc_text = docs[idx]
        doc_id, topic, age_group, domain = meta[idx]
        retrieved_chunks.append(
            RetrievedChunk(
                content=doc_text,
                topic=topic,
                age_group=age_group,
                domain=domain,
                score=score,
            )
        )

    return SearchResponse(query=req.query, retrieved=retrieved_chunks)

if __name__ == "__main__":
    # For development only; in production use uvicorn/gunicorn with proper process management.
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

> الكود أعلاه يعمل بالكامل محلياً، ويستخدم نماذج تضمين محفوظة في الـ cache المحلي (أو مجلّد النماذج) دون إرسال أي نص أو تضمين إلى خارج الشبكة؛ أي استخدام خارجي لـ Hugging Face يجب أن يتم بواسطة تنزيل مسبق يدوي للنموذج إلى الخادم المنزلي.

### 2.3 Reranking Layer (Arabic Cross-Encoder)

- يمكن تحسين جودة الاسترجاع بإضافة طبقة **Reranker** عربية مبنية على Cross‑Encoder مثل `ARA-Reranker-V1`، المصمم خصيصاً لإعادة ترتيب النتائج العربية بناءً على ترابط (سؤال، فقرة). [huggingface](https://huggingface.co/Omartificial-Intelligence-Space/ARA-Reranker-V1)
- [استدلال] تُستخدم خطوة الـ Reranking فقط على أعلى N نتائج (مثلاً 20) من طبقة BGE‑M3، حيث يقوم Cross‑Encoder بقراءة كل زوج (استعلام، فقرة) وإرجاع درجة صلة، ثم تُستخدم هذه الدرجة لإعادة ترتيب النتائج قبل تمريرها للنموذج اللغوي؛ هذا سلوك متوقع، وليس مضموناً. [towardsdatascience](https://towardsdatascience.com/advanced-rag-retrieval-cross-encoders-reranking/)
- هذا الأسلوب (Bi‑encoder للترشيح ثم Cross‑encoder لإعادة الترتيب) موصى به في أنظمة RAG المتقدمة لتحقيق توازن بين الكلفة وجودة النتائج. [reddit](https://www.reddit.com/r/Rag/comments/1s8j0im/reranker_worsening_rag_retrieval_results/)

***

## 3. Zero-Telemetry Context Engine

### 3.1 Local Personalization State Machine (SQLite)

الهدف هنا هو تصميم آلة حالات (State Machine) محلية تحفظ حالة الطفل تربوياً دون أي Telemetry خارجية، مع اعتماد SQLite كمخزن وحيد لهذه الحالة.

#### Data Model in SQLite (Local Only)

جداول مقترحة (كلها محلية على خادم Ollama/الخادم المنزلي):

1. **children**
   - `child_id` (INTEGER, PK)
   - `age_group` (TEXT) – مثل "4-6", "7-9", "10-12"
   - `preferred_tone` (TEXT) – مثل "gentle", "firm-but-kind" [استدلال]
   - يتم ربط الطفل بالحساب محلياً فقط (لا تُخزَّن أسماء حقيقية إذا أراد الوالدان ذلك).

2. **domains**
   - `domain_id` (INTEGER, PK)
   - `code` (TEXT UNIQUE) – مثل "screen_time", "prayer", "anger_management"
   - `description` (TEXT)

3. **progress_vectors**
   - `child_id` (FK → children)
   - `domain_id` (FK → domains)
   - `stage` (REAL) – 0.0–1.0 تمثل التقدّم في هذا المجال
   - `last_session_at` (TIMESTAMP)
   - `flags` (TEXT) – JSON صغير لتسجيل ملاحظات مثل "struggles_with_boundaries" [استدلال]
   - مفتاح مركب (child_id, domain_id)

4. **sessions**
   - `session_id` (INTEGER, PK)
   - `child_id` (FK)
   - `domain_id` (FK)
   - `created_at` (TIMESTAMP)
   - `local_only_metadata` (TEXT) – مثال: نوع الجهاز، لا يُسمح بأي معرفات خارجية.[استدلال]

> لا يتم إنشاء أي جدول analytics منفصل، ولا يُسمح بحقول مثل `external_user_id` أو `tracking_id`؛ جميع المعرّفات تبقى محلية ومجرد أعداد داخليّة.[استدلال]

#### State Machine (Logical View)

[استدلال] يمكن توصيف آلة الحالات كما يلي؛ هذا سلوك متوقع، وليس مضموناً:

- **Idle → SessionStarted:**
  - عند بدء جلسة لطفل معيّن في مجال معين، يتم:
    - إنشاء سجل في sessions.
    - تحميل `age_group`, وprogress_vector للمجال المطلوب.
- **SessionStarted → Coaching:**
  - يتم بناء سياق LLM اعتماداً على:
    - عمر الطفل.
    - المجال (مثل: إدارة الغضب).
    - مستوى التقدم (stage) ورمزه (مثلاً: Beginner / Intermediate / Advanced).
- **Coaching → SessionEnded:**
  - بعد انتهاء الإجابات والحوار، تُحدَّث `progress_vectors.stage` اعتماداً على تقييم بسيط للأداء (مثل عدد المحاولات الصحيحة/الخاطئة، تقييم الوالد).
- **SessionEnded → Idle:**
  - لا تُحفظ أي سجلات تفاعلية نصية بصيغة يمكن الربط بينها وبين هوية خارجية، إلا إذا اختار الوالدان تفعيل “سجل محلي”.

### 3.2 Context Assembly & Prompt Injection (On-Device)

لضمان عدم توليد أي بصمات تتبعية (Analytical Footprints)، يتم بناء سياق LLM بالكامل داخل نفس خادم FastAPI/SQLite بدون إرسال أي جزء إلى خارج الشبكة.

#### Context Assembly Algorithm (High-Level)

> الخطوات التالية [استدلال] حول كيفية بناء الـ System Prompt والمحتوى السياقي؛ هذا سلوك متوقع، وليس مضموناً.

1. **استرجاع الحالة من SQLite:**
   - استعلام بـ `child_id` و `domain_code`:
     - `age_group`
     - `progress_vectors.stage`
     - أي `flags` تربوية ذات صلة (مثل الحساسية للوم المباشر).

2. **تجميع سياق مختصر (Context Summary):**
   - مثال (إنجليزي لمواءمة مع النموذج، مع إمكانية تعريب كامل لاحقاً):

   ```text
   Child profile:
   - Age group: 7-9
   - Domain: anger_management
   - Progress stage: 0.4 (early learner)
   - Sensitivity flags: prefers supportive language, avoid harsh blame.

   Parenting philosophy: Islamic, mainstream Sunni, focus on mercy, wisdom, and gradual habit-building.
   ```

3. **حقن السياق في الـ System Prompt:**
   - يتم توليد System Prompt ثابت يحتوي على:
     - تعليمات ثابتة حول المنهج الإسلامي المعتمد (مرجعيّة خارج هذا الملف).
     - إرشادات لغوية: تبسيط اللغة، تجنب المصطلحات المعقدة، دعم الوالد/الطفل.
   - يُضاف ملخص الحالة في بداية الـ System Prompt قبل أي رسائل للمستخدم.

4. **دمج نتائج RAG:**
   - يتم استدعاء `/search` من RAG API السابق مع المعلمات:
     - `query` من الوالد.
     - `age_group` و `domain` من SQLite.
   - تُبنى فقرة “Knowledge Context” من أعلى K مقاطع مع citations داخلية (محلية)، تمرَّر جميعها للنموذج كـ System / Tool context.

5. **عدم تخزين Prompt/Response:**
   - لا يتم حفظ أي prompts أو outputs في SQLite إلا إذا فعِّل “سجل محلي” صريح.
   - في سجل محلي، يمكن حفظ نص الجلسة بعد إزالة أي بيانات تعريفية (مثل الأسماء الحقيقية) باستخدام نفس طبقة الـ Scrubber المستخدمة لاحقاً في الهجرة السحابية.[استدلال]

***

## 4. Confidential Cloud Migration Framework

> هذا القسم يصف إطاراً هندسياً [استدلال] للهجرة السحابية مع الحفاظ على عقد الخصوصية (عدم خروج بيانات الطفل الخام خارج الحدود المحلية قدر الإمكان)، مع الاستفادة من تقنيات Confidential Computing وTEE؛ هذا سلوك متوقع، وليس مضموناً.

### 4.1 Migration Phases & Anonymization / Prompt-Scrubbing

#### Phase 0 – Pure Local (Current Baseline)

- كل شيء يعمل عبر:
  - Ollama على عقدة Tailscale المنزلية (`100.109.163.64:11434`).
  - FastAPI + SQLite + RAG + LLM محلي.
- لا يوجد أي اتصال خارجي باستثناء تحديثات يدويّة للنماذج/البرمجيات من قبل مدير النظام (خالد مثلاً) عبر SSH أو تحميل يدوي.[استدلال]

#### Phase 1 – Hybrid Inference with Strict Anonymization

في حال الحاجة مستقبلاً لاستدعاء نموذج سحابي (أكبر أو أحدث) لبعض الحالات الخاصة (مثلاً مراجعة إجابات عالية الحساسية):

1. **Local Scrubber Layer (Pre-Cloud):**
   - وحدة Python داخل FastAPI تقوم بـ:
     - إزالة الأسماء والألقاب والرموز الشخصية من النص (Regex + نموذج NER محلي إن لزم).[استدلال]
     - تجميع حالة الطفل إلى صفات عامة:
       - `age_group` بدلاً من العمر الدقيق.
       - `progress_bucket` (مثل: low / medium / high) بدلاً من قيمة stage الدقيقة.
       - تحويل `flags` إلى عبارات عامة مثل “child is sensitive to scolding”.[استدلال]

2. **Prompt Template Sent to Cloud:**
   - مثال:

   ```text
   User: parent
   Child profile (generalized):
   - Age group: 7-9
   - Domain: anger_management
   - Progress: early learner (low mastery)

   Question:
   [Redacted, anonymized parenting question text...]

   Constraints:
   - Answer in Modern Standard Arabic.
   - Align with mainstream Islamic parenting principles, focusing on mercy and wisdom.
   ```

   لا يُرسل أي `child_id` أو معرف داخلي أو سياق RAG خام؛ فقط خلاصة معرفية مجردة.[استدلال]

3. **Cloud Response Sanitization (Post-Cloud, Local):**
   - طبقة بعد الاستجابة تقوم بالتحقق من:
     - عدم احتواء الرد على أي استنتاجات خطرة (تستخدم فلتر محلي).
     - عدم مخالفة السياسة الشرعية المعتمدة (يمكن لاحقاً استخدام نموذج محلي صغير للمراجعة).[استدلال]

4. **Strict Network Controls:**
   - يسمح فقط لـ FastAPI بالتواصل مع endpoint سحابي محدد عبر Tailscale/VPN.
   - تعطيل أي Telemetry/Logging في مزود السحابة قدر الإمكان، مع التعاقد على بنية “No-Log” في سياسة المزود.[استدلال]

#### Phase 2 – Full Confidential Computing (TEE/Enclaves)

- استخدام منصّات مثل:
  - [استدلال] **AWS Nitro Enclaves**، **Azure Confidential Computing**، أو **GCP Confidential VMs** حيث يتم تنفيذ النموذج داخل Enclave معزول على مستوى العتاد، ويقدّم تقرير Attestation يمكن التحقق منه؛ هذا سلوك متوقع، وليس مضموناً.
- النتائج المحتملة:
  - يمكن حينها إرسال سياق أكثر تفصيلاً (لكن ما يزال منقَّحاً) مع ضمان تشفّره أثناء المعالجة وحتى في الذاكرة.[استدلال]
  - مع ذلك، يظل عقد Tutor Guardian متمسكاً بمبدأ:
    - “لا بيانات تعريفية شخصية (PII) للطفل” حتى داخل الـ Enclave، إلا عند وجود اتفاق قانوني واضح ومراجعة أمنية مستقلة.[استدلال]

### 4.2 TEE-Based Deployment Pattern (High-Level)

نمط معماري مقترح عند الانتقال إلى TEE:

1. **Local Gateway (On-Prem / Home Server):**
   - FastAPI يعمل كبوابة惟惟:
     - يستقبل طلبات التطبيق (Flutter).
     - يجري RAG المحلي والتخصيص (state machine في القسم 3).
     - يُنفّذ الـ prompt scrubbing وإخفاء الهوية.[استدلال]

2. **Remote TEE Inference Service:**
   - خدمة سحابية داخل Enclave:
     - تستقبل فقط الـ prompts المنقَّحة.
     - لا تمتلك القدرة على تسجيل العناوين IP الحقيقية لو تم استخدام Tailscale/Proxy بشكل مناسب.[استدلال]
     - تُفعّل إعدادات “no persistent storage” قدر الإمكان.

3. **Mutual TLS + Remote Attestation:**
   - قبل إرسال أي طلب:
     - يتحقق FastAPI من Attestation Report للـ Enclave (نوعاً من “شهادة” تثبت أن الكود الذي يعمل هو الكود المتفق عليه).[استدلال]
     - إذا فشل التحقق، يتم رفض الطلب محلياً.

4. **Policy Engine (Local):**
   - طبقة محلية (Python) تطبّق سياسات:
     - ما هو الحد الأقصى لحجم النص المسموح بإرساله.
     - ما هي المجالات (Domains) المسموح بإرسالها للسحابة (مثلاً: استشارات عامة، وليس حالات حساسة جدّاً).[استدلال]
     - إمكانية تعطيل المسار السحابي بالكامل من لوحة تحكم الوالد.

> في جميع المراحل، يظل المبدأ الحاكم هو: أي انتقال من “محلي بالكامل” إلى “هجين” أو “TEE سحابي” يجب أن يتم بقرار واعٍ من صاحب النظام (مثل خالد حمدي السبع) مع توثيق واضح لما يغادر البيئة المحلية وكيف تم إخفاء هويته؛ أي افتراضات في هذا الملف حول الأمان السحابي هي [استدلال] وليست ضمانات مطلقة، وهذا سلوك متوقع، وليس مضموناً.
