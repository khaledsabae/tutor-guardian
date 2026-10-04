"""
Methodology & Sources page — «منهجيتنا ومصادرنا».

Serves a public HTML page explaining the AI methodology, knowledge sources,
and safety guardrails (growth plan §7.2).

Every sentence states what the code does, nothing more. This is a solo
project with no sharia board and no human reviewer, so the page claims the
automated guards and the fiqh deferral — never supervision or review it does
not have. The knowledge-base numbers are counted, not typed.

Route: GET /methodology
"""
from __future__ import annotations

import html as _html
import logging
from collections import Counter

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services.attribution import attribute_visit, cache_control

logger = logging.getLogger(__name__)
router = APIRouter(tags=["web"])

_TEAL = "#01696F"
_CREAM = "#FAF7F2"


def _page(title: str, desc: str, body: str, canonical: str,
          cache: str = "public, max-age=3600") -> HTMLResponse:
    t, d = _html.escape(title), _html.escape(desc)
    doc = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t} — المربّي</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<meta property="og:type" content="website">
<meta property="og:site_name" content="المربّي">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta name="twitter:card" content="summary">
<style>
  :root {{ --teal: {_TEAL}; --cream: {_CREAM}; --charcoal: #1c1c1c; --muted: #6b6b6b; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Cairo', -apple-system, system-ui, sans-serif; background: var(--cream); color: var(--charcoal); line-height: 1.8; }}
  .wrap {{ max-width: 780px; margin: 0 auto; padding: 24px 18px 80px; }}
  h1 {{ font-size: 28px; font-weight: 800; color: var(--teal); margin-bottom: 8px; }}
  h2 {{ font-size: 20px; font-weight: 700; color: var(--teal); margin: 32px 0 12px; padding-top: 16px; border-top: 1px solid rgba(1,105,111,.12); }}
  h3 {{ font-size: 16px; font-weight: 700; margin: 16px 0 8px; }}
  p {{ margin-bottom: 14px; color: #333; }}
  .subtitle {{ color: var(--muted); font-size: 15px; margin-bottom: 24px; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin: 18px 0; }}
  .stat {{ background: white; border-radius: 14px; padding: 18px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,.06); }}
  .stat-num {{ font-size: 28px; font-weight: 800; color: var(--teal); }}
  .stat-label {{ font-size: 13px; color: var(--muted); margin-top: 4px; }}
  ul {{ padding-right: 20px; margin: 10px 0 14px; }}
  li {{ margin-bottom: 8px; }}
  .badge {{ display: inline-block; background: rgba(1,105,111,.1); color: var(--teal); border-radius: 8px; padding: 4px 12px; font-size: 13px; font-weight: 600; margin: 4px 4px 4px 0; }}
  .cta {{ display: block; text-align: center; background: var(--teal); color: white; padding: 16px; border-radius: 14px; text-decoration: none; font-weight: 700; font-size: 17px; margin-top: 32px; }}
  .cta:hover {{ opacity: .92; }}
  .footer {{ text-align: center; color: var(--muted); font-size: 13px; margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(0,0,0,.08); }}
</style>
</head>
<body>
<div class="wrap">
  {body}
  <div class="footer">
    المربّي — تربية إسلامية متكاملة · مجاني بالكامل لوجه الله<br>
    © 2026 Alsaba Cloud
  </div>
</div>
</body>
</html>"""
    return HTMLResponse(content=doc, status_code=200,
                        headers={"Cache-Control": cache})


_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _ar(n: int) -> str:
    """1673 → «١٬٦٧٣», the way the page has always shown its numbers."""
    return f"{n:,}".replace(",", "٬").translate(_AR_DIGITS)


_STATS: dict | None = None  # set once counted; a failed count is retried


def _kb_stats() -> dict | None:
    """Counted from the knowledge base the assistant retrieves from.

    The page used to type its numbers in, and they drifted: «١٬١١٩ وحدة» when
    there were 1,673, and 57 development units when there were 172. Counted
    once per process — the knowledge base only changes with a deploy — but only
    once it succeeds: a failed load is retried on the next request instead of
    hiding the numbers until a restart. "Has a reference" uses the filter that
    decides whether an answer shows a «📚» line, so the page and the answers
    cannot disagree.
    """
    global _STATS
    if _STATS is not None:
        return _STATS
    try:
        from app.services.knowledge_loader import load_default_knowledge_units
        from app.services.llm_service import usable_reference

        units = load_default_knowledge_units()
    except Exception:  # noqa: BLE001 — the page renders without its numbers
        logger.warning("methodology: knowledge-base stats unavailable", exc_info=True)
        return None
    if not units:
        return None
    by_domain = Counter(u.domain for u in units)
    referenced = sum(1 for u in units if usable_reference(u.reference_info))
    _STATS = {
        "total": len(units),
        "islamic": by_domain["islamic_parenting"] + by_domain["aqeedah"],
        "health": by_domain["medical"],
        "development": by_domain["development"],
        "cyber": by_domain["cyber"],
        "referenced_pct": round(100 * referenced / len(units)),
    }
    return _STATS


def _stats_html() -> str:
    stats = _kb_stats()
    if not stats:
        return ""
    cards = [
        (stats["total"], "وحدة معرفة"),
        (stats["islamic"], "في التربية الإسلامية والعقيدة"),
        (stats["health"], "في صحة الطفل وسلوكه"),
        (stats["development"], "في نمو الطفل"),
        (stats["cyber"], "في الأمان الرقمي"),
    ]
    grid = "".join(
        f'<div class="stat"><div class="stat-num">{_ar(n)}</div>'
        f'<div class="stat-label">{label}</div></div>'
        for n, label in cards
    )
    return (f'<div class="stat-grid">{grid}</div>'
            f'<p>{_ar(stats["referenced_pct"])}٪ من الوحدات لها مرجع مذكور معها.</p>')


@router.get("/methodology", include_in_schema=False)
def methodology_page(request: Request):
    """Our methodology and sources — public page for parents and reviewers."""
    canonical = str(request.base_url).rstrip("/") + "/methodology"
    play = _html.escape(attribute_visit(request))

    body = f"""
<h1>منهجيتنا ومصادرنا</h1>
<p class="subtitle">كيف تُبنى إجابات المربّي، وما الذي يُفحَص فيها آليًا</p>

<h2>إجابة مبنية على مراجع</h2>
<p>يبني المربّي إجابته من وحدات قاعدة المعرفة التي يسترجعها لسؤالك، ويذكر مراجعها في سطر يبدأ بـ 📚 متى كان لها مرجع مسجَّل. ولا يُصدر فتاوى: أسئلة الأحكام تُحال إلى أهل العلم.</p>

<h2>قاعدة المعرفة</h2>
{_stats_html()}
<ul>
  <li><strong>التربية الإسلامية والعقيدة:</strong> مستخلصة في أغلبها من كتب في التربية الإسلامية، وعنوان الكتاب مرجعها.</li>
  <li><strong>صحة الطفل وسلوكه:</strong> مبنية في أغلبها على منشورات جهات مثل الأكاديمية الأمريكية لطب الأطفال (AAP) ومراكز السيطرة على الأمراض (CDC) ومنظمة الصحة العالمية (WHO) والمعهد الوطني الأمريكي للصحة النفسية (NIMH)، وبعضها محتوى تحريري كُتب للتطبيق ويقول مرجعه ذلك.</li>
  <li><strong>نمو الطفل:</strong> مراحل النمو الجسدي واللغوي والحركي، من منشورات جهات مثل اليونيسف وAAP وCDC.</li>
  <li><strong>الأمان الرقمي:</strong> إرشادات حماية الأطفال على الإنترنت، من منشورات جهات مثل منظمة الصحة العالمية وCommon Sense Media وInternet Matters.</li>
</ul>

<h2>التفسير القرآني</h2>
<p>إذا سألت عن آية بعينها، يجلب المربّي تفسيرها من خدمة <strong>Tafsir MCP</strong> التابعة لمركز تفسير للدراسات القرآنية (تفسير السعدي والتفسير الميسَّر)، ويُضاف نصّه إلى سياق الإجابة إلى جانب قاعدة المعرفة التربوية. وإن تعذّر الوصول إلى الخدمة، بُنيت الإجابة على قاعدة المعرفة وحدها.</p>

<h2>كيف يعمل المربّي</h2>
<h3>١. البحث الدلالي (RAG)</h3>
<p>حين تسأل سؤالًا تربويًا، يبحث المربّي في قاعدة المعرفة عن أقرب الوحدات صلةً بسؤالك، ببحث دلالي يفهم معنى السؤال لا ألفاظه فقط، ويرشّح النتائج حسب الفئة العمرية لطفلك.</p>

<h3>٢. التوليد الموجَّه</h3>
<p>يُطلب من النموذج أن يبني إجابته على الوحدات المسترجَعة وحدها، فتكون:</p>
<ul>
  <li><strong>عملية:</strong> خطوات واضحة تستطيع تنفيذها اليوم</li>
  <li><strong>مناسبة لعمر الطفل:</strong> فطفل في الرابعة غير طفل في الثالثة عشرة</li>
  <li><strong>مذكورة المراجع:</strong> سطر 📚 بمراجع الوحدات التي بُنيت عليها، متى كان لها مرجع</li>
</ul>

<h3>٣. ضوابط آلية</h3>
<ul>
  <li><strong>الحالات الطارئة:</strong> ما يُصنَّف طارئًا لا يُجيب عنه النموذج أصلًا؛ تظهر إحالة فورية إلى مختص أو إلى الطوارئ</li>
  <li><strong>المراجع:</strong> المرجع الفارغ أو غير الصحيح يُحجب ولا يُنسب إلى الإجابة</li>
</ul>

<h2>ضوابط الأمان</h2>
<ul>
  <li><strong>لا فتوى:</strong> أسئلة الحلال والحرام والعقيدة تُحال إلى أهل العلم، ولا يُجيب عنها المربّي</li>
  <li><strong>لا تشخيص طبي:</strong> المربّي لا يشخّص، ويحيلك إلى مختص في الحالات الخطرة</li>
  <li><strong>لا بحث في الإنترنت:</strong> يُطلب من النموذج ألّا يضيف معلومة من خارج الوحدات المسترجَعة</li>
  <li><strong>حرّاس آليون للنصوص الشرعية:</strong> عند كل تعديل في محتوى التطبيق، تُطابَق آيات الأذكار والإشعارات مع نص المصحف، وأحاديثها مع صحيحي البخاري ومسلم لفظًا ورقمًا، ويُمنع في المحتوى الإنجليزي عرض ترجمة على أنها قرآن. وهذه مطابقة آلية للنصوص، لا مراجعة من أهل العلم.</li>
</ul>

<h2>مجاني لوجه الله</h2>
<p>المربّي مجاني بالكامل — بلا إعلانات ولا اشتراكات ولا مشتريات داخلية. تطبيق خيري نبنيه لوجه الله، ولا نبيع بيانات المستخدمين.</p>

<h2>الخصوصية</h2>
<ul>
  <li>يُخفى اسم طفلك قبل أي معالجة سحابية لسؤالك</li>
  <li>التشفير أثناء النقل (HTTPS)</li>
  <li>لا يلزمك حساب: تسجيل الدخول اختياري</li>
  <li>يمكنك طلب حذف بياناتك من خادمنا في أي وقت عبر support@alsaba.cloud</li>
</ul>

<a class="cta" href="{play}">حمّل المربي مجاناً 🤍</a>
"""

    return _page(
        title="منهجيتنا ومصادرنا",
        desc="كيف تُبنى إجابات المربّي: قاعدة معرفة بمراجع مذكورة، وضوابط آلية، ولا فتوى ولا تشخيص طبي.",
        body=body,
        canonical=canonical,
        cache=cache_control(request.query_params),
    )
