#!/usr/bin/env python3
"""Daily-cohort retention + acquisition report from GA4.

Answers the two questions the Meta campaign decision hangs on:
  1. Is the campaign traffic showing up tagged (utm) or still as (direct)?
  2. Does a campaign-heavy cohort retain like the organic baseline?

Baseline as of 2026-08-15: day-1 retention runs 20-28%. The 13 Aug cohort came
back at 5%, but its day-1 fell on a Friday — the weakest weekday for this
audience — so the campaign and the weekday were not separable. Cohorts whose
day-1 lands midweek settle that.

Usage:  python3 scripts/ga4_cohort_report.py [days_back]
"""
import sys
from datetime import date, timedelta

import google.auth.transport.requests as gtr
import requests
from google.oauth2 import service_account

PROPERTY = "541338024"
KEYFILE = "scripts/play_service_account.json"
URL = f"https://analyticsdata.googleapis.com/v1beta/properties/{PROPERTY}:runReport"


def client():
    creds = service_account.Credentials.from_service_account_file(
        KEYFILE, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    creds.refresh(gtr.Request())
    return {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}


def run(headers, body):
    resp = requests.post(URL, headers=headers, json=body, timeout=60)
    if resp.status_code != 200:
        print(f"  ERR {resp.status_code}: {resp.text[:300]}")
        return None
    return resp.json()


def show(report, label):
    print(f"\n=== {label} ===")
    if not report or not report.get("rows"):
        print("  (no rows)")
        return
    dims = [d["name"] for d in report.get("dimensionHeaders", [])]
    mets = [m["name"] for m in report.get("metricHeaders", [])]
    print("  " + " | ".join(dims + mets))
    for row in report["rows"]:
        vals = [d["value"] for d in row.get("dimensionValues", [])]
        vals += [m["value"] for m in row.get("metricValues", [])]
        print("  " + " | ".join(vals))


def main():
    days_back = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    headers = client()
    today = date.today()
    start = today - timedelta(days=days_back)

    # Retention. Anything but cohortSpec double-counts overlapping windows —
    # active7DayUsers split by firstSessionDate gave 7,361 out of a 770 cohort.
    cohorts = [
        {
            "name": str(start + timedelta(days=i)),
            "dimension": "firstSessionDate",
            "dateRange": {
                "startDate": str(start + timedelta(days=i)),
                "endDate": str(start + timedelta(days=i)),
            },
        }
        for i in range(days_back)
    ]
    show(
        run(
            headers,
            {
                "cohortSpec": {
                    "cohorts": cohorts,
                    "cohortsRange": {
                        "granularity": "DAILY",
                        "startOffset": 0,
                        "endOffset": 7,
                    },
                },
                "dimensions": [{"name": "cohort"}, {"name": "cohortNthDay"}],
                "metrics": [
                    {"name": "cohortActiveUsers"},
                    {"name": "cohortTotalUsers"},
                ],
                "orderBys": [
                    {"dimension": {"dimensionName": "cohort"}},
                    {"dimension": {"dimensionName": "cohortNthDay"}},
                ],
            },
        ),
        "daily cohorts (nthDay 0 = install day)",
    )

    date_range = [{"startDate": str(start), "endDate": "today"}]

    # Acquisition. A tagged Play link surfaces the campaign here; until Meta
    # finishes review the campaign traffic still lands under (direct), because
    # the Facebook in-app browser strips the referrer.
    show(
        run(
            headers,
            {
                "dateRanges": date_range,
                "dimensions": [
                    {"name": "date"},
                    {"name": "firstUserSource"},
                    {"name": "firstUserCampaignName"},
                ],
                "metrics": [{"name": "newUsers"}],
                "orderBys": [
                    {"dimension": {"dimensionName": "date"}},
                    {"metric": {"metricName": "newUsers"}, "desc": True},
                ],
                "limit": 60,
            },
        ),
        "new users by source + campaign",
    )

    show(
        run(
            headers,
            {
                "dateRanges": date_range,
                "dimensions": [{"name": "date"}, {"name": "newVsReturning"}],
                "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
                "orderBys": [{"dimension": {"dimensionName": "date"}}],
            },
        ),
        "daily active users",
    )

    # Gate leak watch: UI events from builds below the minimum mean the config
    # fetch failed and the app fell open. Should trend to zero as old builds
    # churn out; the SharedPreferences fix only protects future gate raises.
    show(
        run(
            headers,
            {
                "dateRanges": date_range,
                "dimensions": [{"name": "eventName"}],
                "metrics": [{"name": "activeUsers"}],
                "dimensionFilter": {
                    "andGroup": {
                        "expressions": [
                            {
                                "filter": {
                                    "fieldName": "appVersion",
                                    "inListFilter": {
                                        "values": [
                                            "1.0.29",
                                            "1.0.30",
                                            "1.0.31",
                                            "1.0.32",
                                            "1.0.33",
                                            "1.0.34",
                                            "1.0.35",
                                        ]
                                    },
                                }
                            },
                            {
                                "filter": {
                                    "fieldName": "eventName",
                                    "inListFilter": {
                                        "values": [
                                            "hub_opened",
                                            "home_card_tapped",
                                            "tab_selected",
                                            "lesson_opened",
                                        ]
                                    },
                                }
                            },
                        ]
                    }
                },
            },
        ),
        "gate leak — UI events from blocked builds (want: zero)",
    )


if __name__ == "__main__":
    main()
