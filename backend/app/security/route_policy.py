"""Route inventory for main 5d566611, with the feedback ownership follow-up.

Documentation/test contract only: neither app.main nor AuthMiddleware imports
this table. Every method/path is explicit; new routes never inherit a policy
from a prefix. ``auth`` names the effective authentication layer; ``scope``
names resource context, not a promise that all ownership checks are complete.
Dependencies describe the actual FastAPI graph, including security scopes.
"""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class RoutePolicy:
    auth: str
    scope: str
    endpoint: str
    in_schema: bool | None = True
    dependencies: tuple = ()
    live_child_session: bool = False
    optional: bool = False
    exception: str = ""


_table: dict[tuple[str, str, str], RoutePolicy] = {}


def _add(
    module,
    auth,
    scope,
    rows,
    *,
    kind="api",
    in_schema=True,
    dependencies=(),
    live_child_session=False,
    optional=False,
    exception="",
):
    # Parse literal inventory rows only. Never inspect app.routes here.
    for line in rows.strip().splitlines():
        methods, path, name = line.split()
        endpoint = f"{module}.{name}" if module else name
        for method in methods.split(","):
            key = (kind, method, path)
            if key in _table:
                raise ValueError(f"Duplicate route policy: {key}")
            _table[key] = RoutePolicy(
                auth,
                scope,
                endpoint,
                in_schema,
                dependencies,
                live_child_session,
                optional,
                exception,
            )


_add(
    "fastapi.applications.FastAPI.setup.<locals>",
    "public",
    "public",
    """
    GET,HEAD /openapi.json openapi
    GET,HEAD /docs swagger_ui_html
    GET,HEAD /docs/oauth2-redirect swagger_ui_redirect
    GET,HEAD /redoc redoc_html
""",
    kind="framework",
    in_schema=False,
)

_add(
    "app.routers.health",
    "public",
    "public",
    """
    GET /health health_check
    GET /api/health api_health_check
    GET /api/app-config get_app_config
""",
)

_add(
    "app.routers.assistant",
    "device",
    "session",
    """
    POST /api/assistant/draft draft_reply
    POST /api/assistant/query query_reply
    POST /api/assistant/stream stream_reply
""",
    exception="Device Bearer plus requested session owner check; legacy ownerless sessions remain compatible",
)

_add(
    "app.routers.chat",
    "public",
    "public",
    """
    POST /api/chat/sessions create_session
""",
    exception="Public bootstrap; proof fixes device identity; known-device bare mint conditional on SESSION_MINT_ENFORCE",
)

_add(
    "app.routers.chat",
    "device",
    "device",
    """
    GET /api/chat/sessions list_sessions
""",
)

_add(
    "app.routers.chat",
    "device",
    "session",
    """
    GET /api/chat/sessions/{session_id} get_session
    POST /api/chat/sessions/{session_id}/stop stop_answer
""",
    exception="Device Bearer plus requested session owner check; legacy ownerless sessions remain compatible",
)

_add(
    "app.routers.feedback",
    "public",
    "public",
    """
    POST /api/feedback/app submit_app_feedback
""",
)

_add(
    "app.routers.feedback",
    "ops",
    "ops",
    """
    GET /api/feedback/app list_app_feedback
    GET /api/feedback/digest feedback_digest
    GET /api/feedback/app/{feedback_id}/audio get_app_feedback_audio
    POST /api/feedback/app/{feedback_id}/reply admin_reply
""",
    exception="FEEDBACK_ADMIN_KEY / X-Admin-Key; _require_admin",
)

_add(
    "app.routers.feedback",
    "ops",
    "ops",
    """
    POST /api/feedback/telegram/webhook telegram_webhook
""",
    exception="Telegram shared-secret header and chat allowlist; _require_webhook_secret",
)

_add(
    "app.routers.feedback",
    "device",
    "device",
    """
    GET /api/feedback/replies list_my_replies
    POST /api/feedback/replies/{reply_id}/read mark_reply_read
""",
)

_add(
    "app.routers.feedback",
    "device",
    "session",
    """
    POST /api/feedback submit_feedback
""",
    exception="Device Bearer; session must be owned by device; ownerless legacy session requires exact authenticated session binding",
)

_add(
    "app.routers.program",
    "public",
    "public",
    """
    GET /api/program/paths list_paths
    GET /api/program/paths/{path_id} get_path_detail
    GET /api/program/next-lesson get_next_lesson
    GET /api/program/lessons/{lesson_id} get_lesson_detail
    GET /api/program/lesson-assets/{lesson_id} get_lesson_assets
    GET /api/program/asset-content/{asset_id} get_asset_content
    GET /api/program/search search_curriculum
    GET /api/program/daily-tip get_daily_tip
    GET /api/program/quiz get_quiz
    GET /api/program/story-themes story_themes
""",
)

_add(
    "app.routers.program",
    "device",
    "device",
    """
    GET /api/program/coach-tip get_coach_tip
    POST /api/program/coach-tip/{tip_id}/tap tap_coach_tip
""",
)

_add(
    "app.routers.program",
    "device",
    "child",
    """
    PATCH /api/program/lessons/{lesson_id}/progress patch_lesson_progress
    GET /api/program/monthly-report/{child_id} monthly_report
""",
    exception="Parent Bearer; handler checks owned child (progress permits legacy child_id=0)",
)

_add(
    "app.routers.program",
    "soft",
    "child",
    """
    POST /api/program/story generate_story
""",
    exception="STORY_AUTH_ENFORCE controls mandatory Bearer; ownership checked only with identity and child_id",
)

_add(
    "app.routers.privacy",
    "public",
    "public",
    """
    GET /privacy-policy get_privacy_policy
    GET /delete-account delete_account_page
""",
    in_schema=False,
)

_add(
    "app.routers.privacy",
    "device",
    "device",
    """
    DELETE /api/privacy/memory delete_my_memory
""",
    dependencies=(("app.core.proof.require_device_proof", (), ()),),
)

_add(
    "app.routers.privacy",
    "device",
    "device",
    """
    DELETE /api/privacy/account delete_my_account
""",
    dependencies=(("app.core.proof.require_device_proof_irreversible", (), ()),),
)

_add(
    "app.routers.methodology",
    "public",
    "public",
    """
    GET /methodology methodology_page
""",
    in_schema=False,
)

_add(
    "app.routers.seo",
    "public",
    "public",
    """
    GET /seo/{slug} seo_page
    GET /seo/ seo_index
""",
    in_schema=False,
)

_add(
    "app.routers.web",
    "public",
    "public",
    """
    GET /ui/cinematic.html landing
    GET /ui/index.html landing
    GET /ui/ landing
""",
    in_schema=False,
)

_add(
    "app.routers.web",
    "public",
    "public",
    """
    GET /go landing
    GET / landing
    GET /l/{lesson_id} lesson_page
    GET /p/{path_id} path_page
    GET /sitemap.xml sitemap
    GET /robots.txt robots
""",
)

_add(
    "app.routers.children",
    "device",
    "device",
    """
    POST /api/children create_child
    GET /api/children list_children
    GET /api/children/missions/pending pending_missions
    POST /api/children/missions/confirm confirm_missions
""",
)

_add(
    "app.routers.children",
    "device",
    "child",
    """
    GET /api/children/{child_id}/progress get_child_progress
    GET /api/children/{child_id}/challenge get_challenge
    GET /api/children/{child_id}/screen-usage get_screen_usage
    PUT /api/children/{child_id}/challenge set_challenge
    DELETE /api/children/{child_id}/challenge clear_challenge
    GET /api/children/{child_id}/agreement/clauses/suggested suggested_agreement_clauses
    GET /api/children/{child_id}/agreement get_agreement
    POST /api/children/{child_id}/agreement put_agreement_draft
    POST /api/children/{child_id}/agreement/sign sign_agreement_as_parent
    GET /api/children/{child_id}/today child_day_summary
    GET /api/children/{child_id}/license child_license_summary
    POST /api/children/{child_id}/license/talked child_license_talked
    POST /api/children/{child_id}/license/grant child_license_grant
""",
    exception="Parent Bearer; handler checks owned child (progress permits legacy child_id=0)",
)

_add(
    "app.routers.children",
    "device",
    "child",
    """
    PATCH /api/children/{child_id} update_child
""",
    exception="Parent Bearer; handler checks owned child (progress permits legacy child_id=0); rename conditionally calls require_device_proof_once_enrolled in handler",
)

_add(
    "app.routers.children",
    "device",
    "child",
    """
    DELETE /api/children/{child_id}/progress reset_child_progress
    DELETE /api/children/{child_id} delete_child
""",
    dependencies=(("app.core.proof.require_device_proof_once_enrolled", (), ()),),
    exception="Parent Bearer; handler checks owned child (progress permits legacy child_id=0)",
)

_add(
    "app.routers.child_memory",
    "device",
    "device",
    """
    GET /api/children/memory/settings get_memory_settings
""",
)

_add(
    "app.routers.child_memory",
    "device",
    "device",
    """
    PUT /api/children/memory/settings put_memory_settings
""",
    exception="Device Bearer; enabling memory calls require_device_proof, disabling remains allowed",
)

_add(
    "app.routers.child_memory",
    "device",
    "device",
    """
    GET /api/children/followups/due followups_due
    GET /api/children/followups/{followup_id} get_followup
    POST /api/children/followups/{followup_id}/answer answer_followup
    POST /api/children/followups/{followup_id}/dismiss dismiss_followup
""",
    dependencies=(("app.core.proof.require_device_proof", (), ()),),
)

_add(
    "app.routers.child_memory",
    "device",
    "child",
    """
    GET /api/children/{child_id}/followups child_followups
    GET /api/children/{child_id}/memory list_memory
    POST /api/children/{child_id}/memory add_memory
    PATCH /api/children/{child_id}/memory/{fact_id} patch_memory
    DELETE /api/children/{child_id}/memory/{fact_id} delete_memory_fact
    DELETE /api/children/{child_id}/memory delete_child_memory
""",
    dependencies=(("app.core.proof.require_device_proof", (), ()),),
    exception="Parent Bearer; handler checks owned child (progress permits legacy child_id=0)",
)

_add(
    "app.routers.child_memory",
    "device",
    "child",
    """
    GET /api/children/{child_id}/weekly-plan get_weekly_plan
""",
    exception="Parent Bearer; handler checks owned child (progress permits legacy child_id=0)",
)

_add(
    "app.routers.device_proof",
    "device",
    "device",
    """
    GET /api/device-proof proof_status
    POST /api/device-proof/start proof_start
    POST /api/device-proof/complete proof_complete
""",
)

_add(
    "app.routers.family_programs",
    "device",
    "device",
    """
    GET /api/programs programs_overview
    POST /api/programs/ramadan/marks ramadan_mark
    PUT /api/programs/ramadan/settings ramadan_settings
    GET /api/programs/ramadan/recap ramadan_recap
""",
)

_add(
    "app.routers.family_programs",
    "device",
    "child",
    """
    GET /api/children/{child_id}/ramadan/today ramadan_today
    GET /api/children/{child_id}/ramadan/days/{day} ramadan_day
    GET /api/children/{child_id}/ramadan/fasting ramadan_fasting
    PUT /api/children/{child_id}/ramadan/fasting ramadan_set_fasting
    POST /api/children/{child_id}/ramadan/fasting/practice ramadan_practice
    GET /api/children/{child_id}/prayer-journey prayer_view
    POST /api/children/{child_id}/prayer-journey/enrol prayer_enrol
    PUT /api/children/{child_id}/prayer-journey/stage prayer_stage
    POST /api/children/{child_id}/prayer-journey/graduate prayer_graduate
    DELETE /api/children/{child_id}/prayer-journey prayer_end
    GET /api/children/{child_id}/milestones milestones_list
    GET /api/children/{child_id}/milestones/{key} milestone_one
""",
    exception="Parent Bearer; handler checks owned child (progress permits legacy child_id=0)",
)

_add(
    "app.routers.family_programs",
    "child",
    "child",
    """
    GET /api/value-tracking/child-mode/prayer/today child_prayer_today
    POST /api/value-tracking/child-mode/prayer/claim child_prayer_claim
""",
    live_child_session=True,
)

_add(
    "app.routers.referral",
    "device",
    "device",
    """
    GET /api/referral/me my_referral
    POST /api/referral/claim claim_referral
""",
)

_add(
    "app.routers.support",
    "public",
    "public",
    """
    GET /api/support/transparency get_transparency
""",
)

_add(
    "app.routers.support",
    "device",
    "device",
    """
    POST /api/support/verify verify_purchase
""",
)

_add(
    "app.routers.stats",
    "public",
    "public",
    """
    GET /api/stats/community community_stats
""",
)

_add(
    "app.routers.stats",
    "ops",
    "ops",
    """
    GET /api/stats/ops-llm ops_llm_metrics
""",
    exception="OPS_METRICS_TOKEN / X-Ops-Token; handler fails closed",
)

_add(
    "app.routers.push",
    "device",
    "device",
    """
    POST /api/push/register register_push_token
    GET /api/push/token get_push_token
""",
)

_add(
    "app.routers.identity",
    "device",
    "device",
    """
    POST /api/identity/link-google link_google_identity
    GET /api/identity/me get_identity
""",
)

_add(
    "app.routers.sync",
    "device",
    "device",
    """
    POST /api/sync/upload upload_backup
    GET /api/sync/download download_backup
""",
)

_add(
    "app.routers.daily_routine",
    "device",
    "device",
    """
    GET /api/daily-routine/today get_today
    POST /api/daily-routine/events create_event
    PATCH /api/daily-routine/events/{event_id} update_event
    DELETE /api/daily-routine/events/{event_id} delete_event
    GET /api/daily-routine/summary get_summary
""",
)

_add(
    "app.routers.value_tracking",
    "device",
    "device",
    """
    GET /api/value-tracking/today get_today
    POST /api/value-tracking/events create_event
    DELETE /api/value-tracking/events/{event_id} delete_event
    GET /api/value-tracking/summary get_summary
""",
)

_add(
    "app.routers.habit_templates",
    "device",
    "device",
    """
    POST /api/habit-templates create_template
    GET /api/habit-templates list_templates
    PATCH /api/habit-templates/{template_id} update_template
""",
)

_add(
    "app.routers.child_mode",
    "device",
    "child",
    """
    POST /api/value-tracking/child-web-claims create_child_web_claim
    POST /api/value-tracking/child-sessions create_child_session
""",
    exception="Parent Bearer; _verify_child_ownership before issuing child capability",
)

_add(
    "app.routers.child_mode",
    "child",
    "child",
    """
    POST /api/value-tracking/child-mode/heartbeat child_heartbeat
    GET /api/value-tracking/child-mode/today child_get_today
    POST /api/value-tracking/child-mode/events child_record_event
    GET /api/value-tracking/child-mode/agreement child_read_agreement
    POST /api/value-tracking/child-mode/agreement/acknowledge child_acknowledge_clause
    POST /api/value-tracking/child-mode/agreement/sign child_sign_agreement
    GET /api/value-tracking/child-mode/mission/today child_mission_today
    POST /api/value-tracking/child-mode/mission/claim child_mission_claim
    GET /api/value-tracking/child-mode/license/today child_license_today
    POST /api/value-tracking/child-mode/license/answer child_license_answer
""",
    live_child_session=True,
)

_add(
    "app.routers.child_mode",
    "child",
    "child",
    """
    POST /api/value-tracking/child-mode/session-end child_session_end
""",
    exception="Child-Bearer required; live-budget session exempt",
)

_add(
    "app.routers.child_mode_web",
    "public",
    "child",
    """
    POST /api/child-web/claim-session claim_session
""",
    exception="Public transport, single-use QR claim capability; conditional budget session opened by handler",
)

_add(
    "app.routers.child_mode_web",
    "child",
    "child",
    """
    GET /api/child-web/me web_child_profile
    POST /api/child-web/refresh refresh_web_session
""",
    exception="Child-Bearer required; live-budget session exempt",
)

_add(
    "app.routers.insights",
    "device",
    "device",
    """
    GET /api/insights/parenting get_parenting_insights
""",
)

_add(
    "app.routers.tafsir",
    "public",
    "public",
    """
    GET /api/tafsir/{surah}/{ayah} get_tafsir
    GET /api/tafsir/{surah}/{ayah}/ayah-text get_ayah_text
    GET /api/tafsir/{surah}/{ayah}/nuzool get_nuzool_reason
    GET /api/tafsir/sources get_sources
    POST /api/tafsir/search search
    POST /api/tafsir/search-tafsir search_tafsir
""",
)

_add(
    "app.routers.quranic_linguistics",
    "public",
    "public",
    """
    POST /api/quranic-linguistics/find-root post_find_root
    POST /api/quranic-linguistics/root-verses post_root_verses
    GET /api/quranic-linguistics/topics/{topic_id}/verses get_topic_verses
    GET /api/quranic-linguistics/verses/{verse_key}/qiraat get_verse_qiraat
    GET /api/quranic-linguistics/verses/{verse_key} get_single_verse
""",
)

_add(
    "",
    "public",
    "public",
    """
    MOUNT /child-mode/web child_mode_web
    MOUNT /docs docs
    MOUNT /ui static
    MOUNT /assets mobile_assets
    MOUNT /.well-known well_known
""",
    kind="mount",
    in_schema=None,
    optional=True,
)

_add(
    "app.main",
    "ops",
    "ops",
    """
    POST /api/admin/send-push admin_send_push
""",
    exception="TG_ADMIN_KEY / X-Admin-Key; handler fails closed",
)

ROUTE_POLICIES = MappingProxyType(_table)
