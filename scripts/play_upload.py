#!/usr/bin/env python3
"""
Google Play Store — رفع AAB تلقائي
=====================================
الاستخدام:
  python3 scripts/play_upload.py --track internal
  python3 scripts/play_upload.py --track alpha --notes "إصلاحات عاجلة"
  python3 scripts/play_upload.py --track production --rollout 0.1

المتطلبات:
  pip install google-api-python-client google-auth
  ملف service_account.json بصلاحيات Google Play Developer API

متغيرات البيئة المطلوبة:
  PLAY_SERVICE_ACCOUNT  — مسار ملف service_account.json
                          (افتراضي: scripts/play_service_account.json)
"""

import argparse
import mimetypes
import os
import sys
import time
from pathlib import Path

import httplib2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# ── ثوابت ───────────────────────────────────────────────────────────────────
PACKAGE_NAME = "com.alsaba.almorabbi"
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]
REPO_ROOT = Path(__file__).resolve().parent.parent
AAB_PATH = REPO_ROOT / "mobile/build/app/outputs/bundle/release/app-release.aab"
DEFAULT_SA = REPO_ROOT / "scripts/play_service_account.json"
TRACKS = ("internal", "alpha", "beta", "production")


# ── مساعدات ─────────────────────────────────────────────────────────────────
def _log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def _die(msg: str, code: int = 1) -> None:
    print(f"\n❌  {msg}", file=sys.stderr)
    sys.exit(code)


def _build_service(sa_path: Path):
    if not sa_path.exists():
        _die(
            f"ملف service account غير موجود: {sa_path}\n"
            "  أنشئه من: Google Play Console → Setup → API access → Service accounts"
        )
    creds = service_account.Credentials.from_service_account_file(
        str(sa_path), scopes=SCOPES
    )
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def _bump_version_code() -> int:
    """يقرأ versionCode الحالي من pubspec.yaml ويرجع القيمة الجديدة (+1)."""
    pubspec = REPO_ROOT / "mobile/pubspec.yaml"
    lines = pubspec.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("version:"):
            # مثال:  version: 1.0.0+5
            parts = line.split("+")
            if len(parts) == 2:
                old_code = int(parts[1].strip())
                new_code = old_code + 1
                lines[i] = f"{parts[0]}+{new_code}"
                pubspec.write_text("\n".join(lines) + "\n")
                return new_code
    _die("تعذّر قراءة versionCode من pubspec.yaml")


# ── منطق الرفع ──────────────────────────────────────────────────────────────
def upload(
    track: str,
    notes: str,
    rollout_fraction: float,
    sa_path: Path,
    aab_path: Path,
    dry_run: bool,
) -> None:
    if not aab_path.exists():
        _die(
            f"AAB غير موجود: {aab_path}\n"
            "  شغّل أولاً:  cd mobile && flutter build appbundle --release"
        )

    size_mb = aab_path.stat().st_size / 1_048_576
    print(f"\n📦  AAB: {aab_path.name}  ({size_mb:.1f} MB)")
    print(f"🎯  Track: {track}  |  Package: {PACKAGE_NAME}")

    if dry_run:
        print("\n⚠️   Dry-run — لا يوجد رفع فعلي.")
        return

    service = _build_service(sa_path)
    publisher = service.edits()

    # 1. افتح تعديل جديد
    _log("1/5  فتح edit جديد …")
    edit = publisher.insert(packageName=PACKAGE_NAME, body={}).execute()
    edit_id = edit["id"]

    try:
        # 2. ارفع الـ AAB
        _log("2/5  رفع AAB … (قد يستغرق دقيقتين)")
        media = MediaFileUpload(
            str(aab_path),
            mimetype="application/octet-stream",
            resumable=True,
        )
        aab_resp = (
            publisher.bundles()
            .upload(packageName=PACKAGE_NAME, editId=edit_id, media_body=media)
            .execute()
        )
        version_code = aab_resp["versionCode"]
        _log(f"     ✓ versionCode={version_code}")

        # 3. عيّن الـ track
        _log(f"3/5  إسناد إلى track={track} …")
        release_body = {
            "versionCodes": [str(version_code)],
            "status": "completed" if track != "production" else (
                "inProgress" if rollout_fraction < 1.0 else "completed"
            ),
            "releaseNotes": [{"language": "ar-SA", "text": notes}],
        }
        if track == "production" and rollout_fraction < 1.0:
            release_body["userFraction"] = rollout_fraction

        publisher.tracks().update(
            packageName=PACKAGE_NAME,
            editId=edit_id,
            track=track,
            body={"releases": [release_body]},
        ).execute()

        # 4. تحقق
        _log("4/5  مراجعة …")
        publisher.validate(packageName=PACKAGE_NAME, editId=edit_id).execute()

        # 5. أكمّل التعديل (commit)
        _log("5/5  تأكيد ونشر …")
        publisher.commit(packageName=PACKAGE_NAME, editId=edit_id).execute()

    except HttpError as exc:
        # ألغِ التعديل لو حدث خطأ
        try:
            publisher.delete(packageName=PACKAGE_NAME, editId=edit_id).execute()
        except Exception:
            pass
        _die(f"خطأ من Play API:\n  {exc}")

    rollout_pct = (
        f"{rollout_fraction * 100:.0f}%" if track == "production" else "100%"
    )
    print(f"\n✅  نُشر بنجاح — versionCode={version_code}  rollout={rollout_pct}")
    print(f"    https://play.google.com/console/u/0/developers/app/{PACKAGE_NAME}/tracks/{track}\n")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="ارفع AAB جديد على Google Play Store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--track",
        choices=TRACKS,
        default="internal",
        help="مسار النشر (افتراضي: internal)",
    )
    parser.add_argument(
        "--notes",
        default="تحديث جديد",
        help="ملاحظات الإصدار بالعربية",
    )
    parser.add_argument(
        "--rollout",
        type=float,
        default=1.0,
        metavar="0.0-1.0",
        help="نسبة الطرح للإنتاج (0.1 = 10%، افتراضي: 1.0)",
    )
    parser.add_argument(
        "--aab",
        type=Path,
        default=AAB_PATH,
        help=f"مسار ملف AAB (افتراضي: {AAB_PATH})",
    )
    parser.add_argument(
        "--sa",
        type=Path,
        default=Path(os.environ.get("PLAY_SERVICE_ACCOUNT", DEFAULT_SA)),
        help="مسار ملف service_account.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="تحقق من المدخلات فقط دون رفع فعلي",
    )

    args = parser.parse_args()

    if not 0.0 < args.rollout <= 1.0:
        _die("--rollout يجب أن يكون بين 0.01 و 1.0")

    upload(
        track=args.track,
        notes=args.notes,
        rollout_fraction=args.rollout,
        sa_path=args.sa,
        aab_path=args.aab,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
