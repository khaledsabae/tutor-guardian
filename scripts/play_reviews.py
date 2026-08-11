#!/usr/bin/env python3
"""
تعليقات Google Play — قراءة والرد
==================================

الاستخدام:
  python3 scripts/play_reviews.py list                      # اعرض ما ينتظر ردًا
  python3 scripts/play_reviews.py list --all                # كل التعليقات
  python3 scripts/play_reviews.py draft > replies.json      # سوّد ردودًا للمراجعة
  python3 scripts/play_reviews.py reply --from replies.json # انشر بعد مراجعتها

**الرد يُنشر علنًا باسم التطبيق.** لذلك `draft` و`reply` منفصلان: لا شيء يُنشر
إلا من ملف راجعه إنسان. `--dry-run` يطبع ما سيُنشر دون نشره.

المتطلبات:
  - تفعيل Google Play Android Developer API في مشروع Cloud
  - دعوة حساب الخدمة في Play Console ← المستخدمون والأذونات، بصلاحية
    «الرد على التقييمات»
  - PLAY_SERVICE_ACCOUNT (افتراضي: scripts/play_service_account.json)

ملاحظة من واجهة Play: التعليقات المتاحة عبر الـAPI هي تعليقات آخر أسبوع فقط.
"""

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PACKAGE_NAME = "com.alsaba.almorabbi"
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SA = REPO_ROOT / "scripts/play_service_account.json"

# حد Play للرد الواحد.
MAX_REPLY = 350


def _service():
    sa = os.environ.get("PLAY_SERVICE_ACCOUNT", str(DEFAULT_SA))
    if not Path(sa).exists():
        sys.exit(f"لا يوجد ملف حساب الخدمة: {sa}")
    creds = service_account.Credentials.from_service_account_file(sa, scopes=SCOPES)
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def _fetch(svc, want_all: bool):
    """كل التعليقات، مع ترقيم الصفحات."""
    out, token = [], None
    while True:
        req = svc.reviews().list(packageName=PACKAGE_NAME, maxResults=100, token=token)
        resp = req.execute()
        out.extend(resp.get("reviews", []))
        token = resp.get("tokenPagination", {}).get("nextPageToken")
        if not token:
            break
    if want_all:
        return out
    return [r for r in out if not _has_reply(r)]


def _latest(review):
    return (review.get("comments") or [{}])[0].get("userComment", {}) or {}


def _has_reply(review):
    return any("developerComment" in c for c in review.get("comments") or [])


def _summarise(review):
    uc = _latest(review)
    return {
        "reviewId": review.get("reviewId"),
        "author": review.get("authorName") or "(بدون اسم)",
        "stars": uc.get("starRating"),
        "text": (uc.get("text") or "").strip(),
        "device": uc.get("device"),
        "appVersion": uc.get("appVersionName"),
        "answered": _has_reply(review),
    }


def cmd_list(args):
    svc = _service()
    reviews = [_summarise(r) for r in _fetch(svc, args.all)]
    reviews.sort(key=lambda r: (r["stars"] or 0))
    print(f"عدد التعليقات: {len(reviews)}\n")
    for r in reviews:
        stars = "★" * (r["stars"] or 0) + "☆" * (5 - (r["stars"] or 0))
        print(f"{stars}  {r['author']}  ({r['appVersion'] or '؟'})  {'[مُجاب]' if r['answered'] else ''}")
        if r["text"]:
            print(textwrap.indent(textwrap.fill(r["text"], 78), "    "))
        print(f"    id: {r['reviewId']}\n")


def cmd_draft(args):
    """يطبع JSON للمراجعة — نص الرد فارغ عمدًا ليكتبه إنسان."""
    svc = _service()
    reviews = [_summarise(r) for r in _fetch(svc, args.all)]
    reviews.sort(key=lambda r: (r["stars"] or 0))
    json.dump(
        [{"reviewId": r["reviewId"], "stars": r["stars"], "author": r["author"],
          "review": r["text"], "reply": ""} for r in reviews],
        sys.stdout, ensure_ascii=False, indent=2,
    )
    print()


def cmd_reply(args):
    svc = _service()
    items = json.load(open(args.from_file, encoding="utf-8"))
    pending = [i for i in items if (i.get("reply") or "").strip()]
    if not pending:
        sys.exit("لا يوجد رد مكتوب في الملف — املأ حقل reply أولًا.")

    too_long = [i for i in pending if len(i["reply"]) > MAX_REPLY]
    if too_long:
        for i in too_long:
            print(f"  ✗ {i['reviewId']}: الرد {len(i['reply'])} حرفًا (الحد {MAX_REPLY})")
        sys.exit("قصّر الردود الطويلة أولًا — لم يُنشر شيء.")

    print(f"{'سيُنشر' if not args.dry_run else 'معاينة (بدون نشر)'}: {len(pending)} ردًا\n")
    sent = 0
    for i in pending:
        print(f"  → {i['reviewId']}  ({i.get('stars')}★ {i.get('author','')})")
        print(textwrap.indent(textwrap.fill(i["reply"], 76), "      "))
        if args.dry_run:
            continue
        try:
            svc.reviews().reply(
                packageName=PACKAGE_NAME,
                reviewId=i["reviewId"],
                body={"replyText": i["reply"]},
            ).execute()
            sent += 1
        except HttpError as e:
            print(f"      ✗ فشل: {e}")
    if not args.dry_run:
        print(f"\nنُشر {sent} من {len(pending)}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="اعرض التعليقات")
    p.add_argument("--all", action="store_true", help="بما فيها المُجاب عليها")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("draft", help="أخرج JSON لكتابة الردود فيه")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser("reply", help="انشر الردود من ملف راجعته")
    p.add_argument("--from", dest="from_file", required=True)
    p.add_argument("--dry-run", action="store_true", help="اطبع دون نشر")
    p.set_defaults(func=cmd_reply)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
