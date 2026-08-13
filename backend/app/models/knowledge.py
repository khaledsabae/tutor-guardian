"""
Pydantic model for a single knowledge unit matching the JSON Schema.
"""
import re
from datetime import datetime
from pydantic import BaseModel, Field

# Tags that say where a unit came from, not what it is about: languages,
# publishers, source-file slugs, storage domains. They are legitimate as
# provenance but pure noise inside a retrieval passage — «english» and «nimh»
# match no parent's question, they only dilute the embedding.
_PROVENANCE_TAGS = frozenset({
    "english", "arabic", "translated_to_arabic",
    "nimh", "cdc", "who", "aap", "unicef", "dsm-5", "icd-11",
    "ulwan", "islamhouse", "internet_matters", "rakaiz", "al_minhaj",
    "nabawi", "alukah", "banat",
    "medical", "cyber", "islamic_parenting", "development", "aqeedah",
    "fiqh", "tarbiyah",
})

# Placeholder behaviour/title values that carry no topic at all.
_EMPTY_TOPIC_VALUES = frozenset({"غير محدد", "غير_محدد", "unspecified", "عام"})

_ARABIC_RE = re.compile(r"[؀-ۿ]")
_LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
# Extraction artefacts that ended up in the `title` field of a few units:
# PDF boilerplate and running heads rather than a description of the content.
_JUNK_TITLE_RE = re.compile(
    r"غير قابل للتحليل|^document resume|^draft\b|^information resource$"
    r"|^guidelines on$|^from the national institute|^an overview for parents"
    r"|^child online$|^how do i get help|^•|www\.",
    re.IGNORECASE,
)


def _clean_tag(value: str) -> str:
    """Underscore-joined tags («صعوبات_اجتماعية») tokenize as one opaque word.
    Spaces let both the embedder and BM25 see the parts."""
    return re.sub(r"\s+", " ", (value or "").replace("_", " ")).strip()


class KnowledgeUnit(BaseModel):
    """وحدة معرفة واحدة – طبي / شرعي / تربوي / سيبراني."""

    id: str
    domain: str  # "medical", "fiqh", "tarbiyah", "cyber"
    age_group: str  # "0-3", "4-6", "7-9", "10-12", "13-15", "16-18"
    # 🚨 اللغة كانت تُرمى صامتة. ١,٠٦١ من ١,١٨٧ ملفًا في `knowledge_base/units/`
    # تحمل `language` (٨٣٥ ar · ١٨٣ mixed · ٤٣ en)، وpydantic كان يسقطها لأن
    # الحقل غير معرَّف هنا — فلا الفهرس يعرف لغة الوحدة ولا الاسترجاع يستطيع
    # تمييزها، وسؤال إنجليزي يُسنَد إلى فقرات عربية بالكامل بلا أثر واحد يقول
    # ذلك. الافتراضي "ar" لأن العربية لغة المصدر: ملف بلا وسم عربيٌّ حتى يثبت
    # غيره، لا مجهول.
    language: str = "ar"  # "ar" · "en" · "mixed"
    behavior_type: str
    title: str = ""
    intervention_type: str = "إرشادي"  # "وقائي", "إرشادي", "علاجي", "إحالة_لطبيب"
    severity: str = "خفيف"  # "خفيف", "متوسط", "شديد", "طارئ"
    reference_type: str = ""
    reference_info: str = ""
    jurisdiction: str | None = None
    text_original: str = ""
    text_simplified: str = ""
    labels: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0"
    source_meta: dict | None = None

    # ── Derived text used for retrieval ─────────────────────────────────────

    @property
    def topic_header(self) -> str:
        """One-to-three lines naming what this unit is ABOUT.

        `text_simplified` is authored prose: it explains the advice but rarely
        names its own subject, so a unit titled «نصائح غذائية للأطفال» whose
        body only talks about olive oil and avocado is, to a vector search,
        indistinguishable from any other gentle parenting paragraph. That is
        exactly how it came back as a reference for «ابني بيتكسف يسلم على
        الناس». The topic fields already exist on every unit — they were just
        kept out of the vector. This assembles them.

        Ordering is specific → general: title, then behaviour category, then
        the label/keyword bag. Anything already said by an earlier line is
        dropped, so the header never repeats itself.

        Measured honestly: on a 30-question / 118-pair Arabic benchmark judged
        against a 3-level rubric, this moved precision from 17.8/47.5/34.7
        (on-topic/partial/unrelated) to 19.5/46.6/33.9 — inside the noise. The
        header is strictly more signal at zero query-time cost, but it is not
        the lever. On that benchmark 11 of 30 questions had NO on-topic unit
        anywhere in the corpus, under any retrieval setting tried including an
        unfiltered whole-KB search. Coverage binds before ranking does.
        """
        lines: list[str] = []
        seen = ""

        title = _clean_tag(self.title)
        if (
            title
            and not _JUNK_TITLE_RE.search(title)
            and _LETTER_RE.search(title)
        ):
            lines.append(title)
            seen = title

        behavior = _clean_tag(self.behavior_type)
        if behavior and behavior not in _EMPTY_TOPIC_VALUES and behavior not in seen:
            lines.append(behavior)
            seen = f"{seen} {behavior}"

        tags: list[str] = []
        for raw in [*(self.labels or []), *(self.keywords or [])]:
            tag = _clean_tag(raw)
            if not tag or not _LETTER_RE.search(tag):
                continue
            if raw.strip().lower() in _PROVENANCE_TAGS or tag.lower() in _PROVENANCE_TAGS:
                continue
            if not _ARABIC_RE.search(tag) and tag.lower() in seen.lower():
                continue
            if tag in seen or tag in tags:
                continue
            tags.append(tag)
        if tags:
            lines.append("، ".join(tags))

        return "\n".join(lines)

    @property
    def embedding_text(self) -> str:
        """What actually gets embedded: the topic header, then the body.

        The "passage: " prefix is the multilingual-e5 convention and must stay
        (queries are embedded with "query: ").
        """
        header = self.topic_header
        body = self.text_simplified or ""
        return f"passage: {header}\n{body}" if header else f"passage: {body}"
