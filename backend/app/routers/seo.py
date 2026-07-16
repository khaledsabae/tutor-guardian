"""
SEO pages for common parenting pain-point questions.

Each page targets a specific search query (e.g. "كيف أعلم طفلي الصلاة")
and provides valuable content that ranks organically.

Route: GET /seo/{slug}
"""
from __future__ import annotations

import html as _html
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["web"])

_TEAL = "#01696F"
_CREAM = "#FAF7F2"
_PLAY = "https://play.google.com/store/apps/details?id=com.alsaba.almorabbi"

# SEO page definitions
SEO_PAGES = {
    "pray-child": {
        "title": "كيف أعلم طفلي الصلاة — دليل شامل للآباء",
        "description": "طرق عملية لتعليم الطفل الصلاة والاعتياد عليها من الصفر، مع نصائح تربوية إسلامية موثقة",
        "keywords": "تعليم الصلاة, طفلي لا يصلي, كيف اعلّم ولدي الصلاة, تربية إسلامية",
        "body": """
<h1>كيف أعلم طفلي الصلاة</h1>
<p class="subtitle">دليل شامل للآباء — من الصفر إلى الاعتياد</p>

<h2>لماذا الصلاة مهمة في التربية الإسلامية؟</h2>
<p>الصلاة هي الركن الثاني من أركان الإسلام، وهي أول ما يُحاسب عليه العبد يوم القيامة. تعليم الطفل الصلاة ليس مجرد نقل أفعال جسدية — بل غرس قيمة روحية ترافقه مدى الحياة.</p>

<h2>متى أبدأ بتعليم طفلي الصلاة؟</h2>
<ul>
  <li><strong>من عمر 3 سنوات:</strong> اجعله يجلس معك في الصلاة ولا تُجبره — المراقبة والمحاكاة طبيعية في هذا العمر</li>
  <li><strong>من عمر 5-6 سنوات:</strong> ابدأ بتعليم الأركان تدريجيًا — الطهارة، ثم القبلة، ثم التكبير</li>
  <li><strong>من عمر 7 سنوات:</strong> هذا السن الذي يجب فيه التفريق (حديث «مُروا صبيانكم بالصلاة وهم أبناء سبع»)</li>
</ul>

<h2>خطوات عملية لتعليم الصلاة</h2>
<h3>١. ابدأ بالطهارة</h3>
<p>علم طفلك الوضوء بطريقة مبسطة: غسل اليدين، المضمضة، الاستنشاق، غسل الوجه، غسل الذراعين، مسح الرأس، غسل الرجلين. اجعلها لعبة: "يلينا نتوضأ مع بعض؟"</p>

<h3>٢. علّمه أركان الصلاة</h3>
<ul>
  <li><strong>القيام:</strong> وقف مستقيم نحو القبلة</li>
  <li><strong>التكبير:</strong> "الله أكبر" — ابدأ به وكرره</li>
  <li><strong>القراءة:</strong> اقرأ معه سورة قصيرة (الإخلاص مثلاً)</li>
  <li><strong>الركوع والسجود:</strong> علمه الأفعال الجسدية خطوة بخطوة</li>
  <li><strong>التشهد والسلام:</strong> آخر ما يتعلمه</li>
</ul>

<h3>٣. اجعلها تجربة إيجابية</h3>
<ul>
  <li>صلِّ معه دائمًا — القدوة أقوى من التعليم</li>
  <li>اشتره بتشجيع بعد كل صلاة: "ما شاء الله، صليت زي الكبير!"</li>
  <li>استخدم البطاقات التعليمية والألوان</li>
  <li>لا تعاقبه إذا فاتته صلاة — بل شجّعه على المحاولة التالية</li>
</ul>

<h3>٤. ثبّت العادة</h3>
<ul>
  <li>صلِّ في نفس المكان والوقت كل يوم</li>
  <li>اجعل الاستعداد جزءًا من الروتين: "يلا نتوضأ ونصلي المغرب"</li>
  <li>after الإفطار أو بعد المغرب — أوقات مناسبة للطفل</li>
</ul>

<h2>نصائح إضافية</h2>
<ul>
  <li><strong>لا تُرهق طفلك:</strong> الصلاة المقبولة من طفل 5 سنوات هي صلاة مختصرة (ركعتين)</li>
  <li><strong>احترم مراحل النمو:</strong> الطفل لا يفهم كل التفاصيل الشرعية فورًا</li>
  <li><strong>استخدم التقنية:</strong> تطبيقات تعليم الصلاة للأطفال (مثل المربي الذكي) تجعل التعلم ممتعًا</li>
  <li><strong>ادعُ له:</strong> "اللهم اجعل صلاتي قبولًا" —دعاء الوالدين مستجاب</li>
</ul>

<h2>كيف يساعدك المربي الذكي؟</h2>
<p>المربي الذكي يقدّم لك نصائح تربوية مخصصة لعمر طفلك وتحدياته، مع تأصيل شرعي ومرجع علمي. جرّب اسأل: "طفلي 5 سنين بيرفض الصلاة، أعمل إيه؟" — وستحصل على إجابة عملية موثقة.</p>

<a class="cta" href="%(play)s">حمّل المربي مجاناً 🤍</a>
""" % {"play": _PLAY},
    },
    "tantrums-child": {
        "title": "كيف أتعامل مع نوبات الغضب عند الأطفال — حلول عملية",
        "description": "طرق فعّالة للتعامل مع نوبات الغضب والعناد عند الأطفال من منظور تربوي إسلامي موثق",
        "keywords": "نوبات الغضب, عناد الطفل, كيف أتعامل مع الغضب, تربية الأطفال",
        "body": """
<h1>كيف أتعامل مع نوبات الغضب عند الأطفال</h1>
<p class="subtitle">حلول عملية من منظور تربوي إسلامي موثق</p>

<h2>لماذا يغضب الأطفال؟</h2>
<p>نوبات الغضب عند الأطفال طبيعية وليست علامة على سوء السلوك. الطفل في مرحلة النمو لا يملك أدوات كافية للتعبير عن مشاعره، فالغضب هو الوسيلة الوحيدة التي يعرفها.</p>

<h2>أنواع نوبات الغضب</h2>
<ul>
  <li><strong>نوبات الإحباط:</strong> عندما لا يستطيع الطفل الوصول لشيء يريده</li>
  <li><strong>نوبات التعب:</strong> عند الجوع أو الإرهاق أو النعاس</li>
  <li><strong>نوبات الانتباه:</strong> عندما يريد لفت انتباه الوالد</li>
  <li><strong>نوبات التمرد:</strong> عندما يُطلب منه فعل شيء لا يريد فعله</li>
</ul>

<h2>التعامل الصحيح مع نوبات الغضب</h2>
<h3>١. ابقَ هادئًا أنت أولًا</h3>
<p>"وإذا غضبوا هم يُطفئون غضبهم" — القدوة الهادئة تُهدئ الطفل تلقائيًا. لا تصرخ ولا تضرب.</p>

<h3>٢. اعترف بمشاعره</h3>
<p>"أشوف إنك زعلان/زعلانة" — التسمية المشاعر تُعطي الطفل إحساس بأنه مفهوم.</p>

<h3>٣. انتظر الانتهاء</h3>
<p>لا تحاول التحدث أثناء العاصفة العاطفية. ابقَ بجانبه وانتظر.</p>

<h3>٤. ابحث عن السبب</h3>
<p>بعد الهدوء، اسأل بهدوء: "إيه اللي حصل؟" أو "إزاي أقدر أساعدك؟"</p>

<h3>٥. اعرض بدائل</h3>
<p>"عشان كده زعلان، إيه رأيك نعمل كذا؟" — البديل يُحوّل المواجهة لتعاون.</p>

<h2>ما لا يجب فعله</h2>
<ul>
  <li>❌ العقاب الجسدي أو اللفظي القاسي</li>
  <li>❌ التسوية السريعة (الاستسلام للمطالب)</li>
  <li>❌ تجاهل الطفل تمامًا</li>
  <li>❌ مقارنته بأطفال آخرين</li>
</ul>

<h2>الوقاية خير من العلاج</h2>
<ul>
  <li>روتين يومي ثابت (أكل، نوم، ألعاب)</li>
  <li>خيارات محدودة بدل أوامر كثيرة</li>
  <li>تمديد وقت الانتباه تدريجيًا</li>
  <li>الثناء على السلوك الإيجابي فورًا</li>
</ul>

<h2>كيف يساعدك المربي الذكي؟</h2>
<p>اسأل المربي عن تفاصيل تربوية مخصصة لطفلك — كل طفل فريد، والإجابة العامة لا تكفي. المربي يجيبك بتأصيل شرعي ومرجع علمي.</p>

<a class="cta" href="%(play)s">حمّل المربي مجاناً 🤍</a>
""" % {"play": _PLAY},
    },
    "screen-time-child": {
        "title": "طفلي مشغول بالشاشات — كيف أُقلل وقت الشاشات؟",
        "description": "نصائح عملية لتقليل وقت الشاشات عند الأطفال مع بدائل إبداعية إسلامية",
        "keywords": "وقت الشاشات, طفلي مشغول بالتابلت, إدمان الشاشات, بدائل إبداعية",
        "body": """
<h1>طفلي مشغول بالشاشات</h1>
<p class="subtitle">نصائح عملية لتقليل وقت الشاشات مع بدائل إبداعية</p>

<h2>لماذا الشاشات تجذب الأطفال؟</h2>
<p>الشاشات تعمل على نظام "المكافأة الفورية" — صور متحركة، ألوان زاهية، أصوات مثيرة. المخ يبحث عن المكافأة السريعة بطبيعته، الطفل ليس ضعيف الإرادة — بل مخه مُprogrammed للبحث عن هذا النمط.</p>

<h2>الحلول العملية</h2>
<h3>١. حدود واضحة ومتفق عليها</h3>
<ul>
  <li>حدد وقتًا محددًا (ساعة صباحًا وساعة مساءً مثلاً)</li>
  <li>استخدم مؤقت بصري (مؤقت ملون أو ساعة رملية)</li>
  <li>اتفق مع الطفل على القواعد قبل البدء</li>
</ul>

<h3>٢. بديل مشوق</h3>
<ul>
  <li>ألعاب تفاعلية (اللعبة التعليمية في المربي الذكي مثال)</li>
  <li>قراءة قصة مشتركة</li>
  <li>نشاط حركي في الخارج</li>
  <li>أعمال يدوية إبداعية</li>
</ul>

<h3>٣. بيئة خالية من المشتتات</h3>
<ul>
  <li>أزل الأجهزة من غرفة النوم</li>
  <li>اجعل أوقات الأكل خالية من الشاشات</li>
  <li>كن أنت المثال (لا تستخدم هاتفك أمام الطفل دائمًا)</li>
</ul>

<h3>٤. المكافأة على البديل</h3>
<ul>
  <li>شجّع النشاط البديل بالثناء والعملات</li>
  <li>سجّل التقدم في بطاقة العادات (موجودة في المربي الذكي)</li>
</ul>

<h2>كم من الوقت مقبول؟</h2>
<p>الأبحاث تشير إلى:</p>
<ul>
  <li><strong>أقل من سنتين:</strong> لا شاشات إطلاقًا (إلا المكالمات العائلية)</li>
  <li><strong>2-5 سنوات:</strong> ساعة كحد أقصى يوميًا</li>
  <li><strong>6+ سنوات:</strong> ساعتان مع فترات راحة كل 20 دقيقة</li>
</ul>

<h2>كيف يساعدك المربي الذكي؟</h2>
<p>اسأل المربي عن خطة مخصصة لطفلك — كل طفل مختلف، وما ينفع مع واحد قد لا ينفع مع آخر.</p>

<a class="cta" href="%(play)s">حمّل المربي مجاناً 🤍</a>
""" % {"play": _PLAY},
    },
    "child-eating-refusal": {
        "title": "طفلي يرفض الأكل — أسباب وحلول عملية",
        "description": "لماذا يرفض الطفل الأكل وكيف أتعامل مع رفض الطعام بشكل إيجابي",
        "keywords": "طفلي يرفض الأكل, نفوق الطفل, إدمان الطعام, تربية الأطفال",
        "body": """
<h1>طفلي يرفض الأكل</h1>
<p class="subtitle">أسباب وحلول عملية لرفض الطعام عند الأطفال</p>

<h2>لماذا يرفض الطفل الأكل؟</h2>
<p>رفض الطعام عند الأطفال سلوك شائع وطبيعي في أغلب الأحيان. الأسباب المحتملة:</p>
<ul>
  <li><strong>مرحلة نمو طبيعية:</strong> الشهية تتذبذب مع النمو</li>
  <li><strong>إرهاق أو مرض:</strong> الطفل قد يكون متعبًا أو مريضًا</li>
  <li><strong>إجهاد أو توتر:</strong> تغيير في الروتين أو الانتقال</li>
  <li><strong>مجرد التمرد:</strong> الطفل يريد السيطرة على اختياره</li>
</ul>

<h2>الحلول العملية</h2>
<h3>١. لا تُجبر الطفل</h3>
<p>الإجبار يزيد المشكلة. اعرض الطعام واترك الاختيار للطفل.</p>

<h3>٢. اجعل الطعام مشوقًا</h3>
<ul>
  <li>استخدم ألوان طبيعية مختلفة</li>
  <li>قدم الطعام بأشكال ممتعة</li>
  <li>اسمح للطفل بالمساعدة في التحضير</li>
</ul>

<h3>٣. روتين منظم</h3>
<ul>
  <li>3 وجبات رئيسية + 2 وجبة خفيفة</li>
  <li>فاصل 2-3 ساعات بين الوجبات</li>
  <li>لا مشروبات ساخنة أو معلبات قبل الأكل</li>
</ul>

<h3>٤. نموذج سلوكي</h3>
<ul>
  <li>كل أمام الطفل</li>
  <li>أظهر الاستمتاع بالأكل</li>
  <li>اثن على الطفل عندما يأكل</li>
</ul>

<h2>متى أقلق؟</h2>
<ul>
  <li>نقص وزن ملحوظ</li>
  <li>تأخر في النمو</li>
  <li>إرهاق مستمر</li>
  <li>في هذه الحالة، استشر طبيب الأطفال</li>
</ul>

<h2>كيف يساعدك المربي الذكي؟</h2>
<p>اسأل المربي عن خطة مخصصة لطفلك — المربي يعرف إن طفل 3 سنوات يختلف عن طفل 8 سنوات.</p>

<a class="cta" href="%(play)s">حمّل المربي مجاناً 🤍</a>
""" % {"play": _PLAY},
    },
}


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
  ul {{ padding-right: 20px; margin: 10px 0 14px; }}
  li {{ margin-bottom: 8px; }}
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


@router.get("/seo/{slug}", include_in_schema=False)
async def seo_page(request: Request, slug: str):
    """SEO page for a specific pain-point question."""
    if slug not in SEO_PAGES:
        return HTMLResponse(content="Page not found", status_code=404)
    
    page_data = SEO_PAGES[slug]
    canonical = str(request.base_url).rstrip("/") + f"/seo/{slug}"
    
    return _page(
        title=page_data["title"],
        desc=page_data["description"],
        body=page_data["body"],
        canonical=canonical,
    )


@router.get("/seo", include_in_schema=False)
async def seo_index(request: Request):
    """Index of all SEO pages."""
    base_url = str(request.base_url).rstrip("/")
    
    links = []
    for slug, data in SEO_PAGES.items():
        links.append(f'<li><a href="{base_url}/seo/{slug}">{data["title"]}</a></li>')
    
    body = f"""
<h1>نصائح تربوية — المربّي</h1>
<p class="subtitle">مقالات مفيدة للآباء من خبراء التربية الإسلامية</p>

<h2>المقالات</h2>
<ul>
{"".join(links)}
</ul>

<a class="cta" href="{_PLAY}">حمّل المربي مجاناً 🤍</a>
"""
    
    return _page(
        title="نصائح تربوية — المربّي",
        desc="مقالات مفيدة للآباء من خبراء التربية الإسلامية — تربية إسلامية متكاملة",
        body=body,
        canonical=base_url + "/seo",
    )
