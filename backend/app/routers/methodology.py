"""
Methodology & Sources page — «منهجيتنا ومصادرنا».

Serves a public HTML page explaining the AI methodology, knowledge sources,
and safety guardrails. Strategic counter to Babymode's announced "sharia board"
differentiator (growth plan §7.2).

Route: GET /methodology
"""
from __future__ import annotations

import html as _html
import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"])

_TEAL = "#01696F"
_CREAM = "#FAF7F2"
_PLAY = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"


def _page(title: str, desc: str, body: str, canonical: str) -> HTMLResponse:
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
                        headers={"Cache-Control": "public, max-age=3600"})


@router.get("/methodology", include_in_schema=False)
async def methodology_page(request: Request):
    """Our methodology and sources — public page for parents and reviewers."""
    canonical = str(request.base_url).rstrip("/") + "/methodology"

    body = """
<h1>منهجيتنا ومصادرنا</h1>
<p class="subtitle">كيف نضمن أن إجابات المربي موثوقة وآمنة لطفلك</p>

<h2>الإجابة المؤصّلة — مش مجرد كلام</h2>
<p>كل إجابة يعطيها المربي مبنية على <strong>مصادر موثّقة</strong>، و<strong>مذكّر فيها المصدر</strong> في سطر خاص يبدأ بـ 📚. لا نخترع معلومات، ولا نُصدر فتاوى بدون سند.</p>

<h2>قاعدة المعرفة</h2>
<div class="stat-grid">
  <div class="stat">
    <div class="stat-num">١٬١٢٢</div>
    <div class="stat-label">وحدة معرفة</div>
  </div>
  <div class="stat">
    <div class="stat-num">٥٥٥</div>
    <div class="stat-label">وحدة شرعية</div>
  </div>
  <div class="stat">
    <div class="stat-num">٢٥١</div>
    <div class="stat-label">وحدة سيبرانية</div>
  </div>
  <div class="stat">
    <div class="stat-num">٢٥٩</div>
    <div class="stat-label">وحدة طبية</div>
  </div>
</div>
<p>كل وحدة معرفية في قاعدة البيانات موثّقة بمصدرها — كتاب مرجع، أو حديث نبوي، أو مرجع تربوي متخصص. الوحدات مُقسّمة إلى مجالات:</p>
<ul>
  <li><strong>شرعي (تربية إسلامية + عقيدة):</strong> أحاديث نبوية، آيات قرآنية، أقوال العلماء — موثّقة بالمرجع الكامل</li>
  <li><strong>سيبراني (أمن رقمي):</strong> إرشادات حماية الأطفال الرقمية من مصادر متخصصة</li>
  <li><strong>طبي (سلوك ونفسية):</strong> إرشادات السلوك والصحة النفسية من مراجع طبية موثوقة</li>
  <li><strong>تطوّر الطفل:</strong> مراحل النمو الجسدي واللغوي والحركي (٥٧ وحدة)</li>
</ul>

<h2>كيف يعمل المربي</h2>
<h3>١. البحث الدلالي (RAG)</h3>
<p>لما تسأل سؤالاً تربوياً، المربي يبحث في قاعدة المعرفة عن أقرب الوحدات المعرفية صلةً بسؤالك — باستخدام تقنية البحث الدلالي (Semantic Search) اللي بتفهم معنى سؤالك مش بس الكلمات.</p>

<h3>٢. التوليد الموجّه</h3>
<p>المربي لا يخترع إجابات من فراغ. هو يأخذ الوحدات المعرفية الموثّقة ويولّد منها إجابة عملية مخصصة لعمر طفلك وتحديتك. الإجابة تكون:</p>
<ul>
  <li><strong> عملية:</strong> خطوات واضحة تقدر تنفذها اليوم</li>
  <li><strong>مناسبة لعمر الطفل:</strong> المربي يعرف إن طفل ٤ سنين يختلف عن طفل ١٣ سنة</li>
  <li><strong>مذكّر بالمصدر:</strong> كل إجابة فيها سطر 📚 المصدر</li>
</ul>

<h3>٣. بوابات الجودة</h3>
<p>قبل ما الإجابة توصلك، تمرّ ببوابات فحص تلقائية:</p>
<ul>
  <li><strong>بوابة الأمان:</strong> لا نُقدّم إجابات عن مواضيع طبية حساسة بدون تحويل لطبيب</li>
  <li><strong>بوابة المصدر:</strong> تأكد إن فيه مصدر موثّق ورا الإجابة</li>
  <li><strong>بوابة الملاءمة:</strong> الإجابة مناسبة لعمر الطفل والسياق</li>
</ul>

<h2>ضوابط الأمان (Guardrails)</h2>
<ul>
  <li><strong>لا نُفتي:</strong> المربي لا يُقدّم فتاوى شخصية في الحلال والحرام — يحيل لعلماء مختصين</li>
  <li><strong>لا تشخيص طبي:</strong> المربي يرشدك لطبيب متخصص لما يكون الموضوع طبياً (التبول اللاإرادي، الخوف، الإدمان)</li>
  <li><strong>حصر في المحتوى الموثّق:</strong> الإجابة مبنية على المصادر الموجودة في قاعدة المعرفة فقط — لا معلومات من الإنترنت العام</li>
  <li><strong>مراجعات دورية:</strong> الوحدات المعرفية تُراجع دورياً للتأكد من صحتها وحداثتها</li>
</ul>

<h2>مجاني لوجه الله</h2>
<p>المربّي مجاني بالكامل — بلا إعلانات، بلا اشتراكات، بلا مشتريات داخلية. تطبيق خيري نبنيه لوجه الله. لا نبيع بيانات المستخدمين ولا نشاركها مع أطراف ثالثة.</p>

<h2>الخصوصية أولاً</h2>
<ul>
  <li>بيانات طفلك تبقى على جهازك — لا تُرسل لخوادمنا إلا عند السؤال (وتُحذف بعد المعالجة)</li>
  <li>لا نجمع بيانات شخصية تُعرّف بهويتك</li>
  <li>التشفير أثناء النقل (HTTPS)</li>
  <li>لا حسابات إجبارية — تطبيق بدون تسجيل دخول</li>
</ul>

<a class="cta" href="%(play)s">حمّل المربي مجاناً 🤍</a>
""" % {"play": _PLAY}

    return _page(
        title="منهجيتنا ومصادرنا",
        desc="كيف يضمن المربي الذكي أن إجاباته موثوقة ومبنية على مصادر شرعية وعلمية — قاعدة معرفة ١٬١٢٢ وحدة مع ضوابط أمان صارمة",
        body=body,
        canonical=canonical,
    )
