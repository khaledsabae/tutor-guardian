"""Shared set-up for the family-program tests (schema v34).

The app is mounted with a stub auth middleware, like the other child-surface
suites: Bearer requests act as DEVICE unless `X-Test-Device` names another;
Child-Bearer requests carry a real child token, so the child half is checked
against the token the way production checks it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.db.init_db import get_conn
from app.routers.children import router as children_router
from app.routers.family_programs import router as programs_router
from app.services import child_token
from app.services import programs_common as pc

DEVICE = "dev-programs-1"
OTHER = "dev-programs-2"


class _AuthStub(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("Authorization", "")
        if header.startswith("Child-Bearer "):
            payload = child_token.verify_child_token(header[13:].strip())
            if payload is None:
                return JSONResponse(status_code=401, content={"detail": "invalid"})
            request.state.child_mode = True
            request.state.device_id = payload["device_id"]
            request.state.child_id = payload["child_id"]
        else:
            request.state.device_id = request.headers.get("X-Test-Device", DEVICE)
        return await call_next(request)


def make_app(with_weekly_plan: bool = False) -> FastAPI:
    app = FastAPI()
    app.add_middleware(_AuthStub)
    app.include_router(children_router, prefix="/api")
    app.include_router(programs_router, prefix="/api")
    if with_weekly_plan:
        # Stands in for PR #26's endpoint: the gate looks for the route.
        extra = APIRouter()

        @extra.get("/children/{child_id}/weekly-plan")
        def _weekly_plan(child_id: int):  # pragma: no cover — never called
            return {}

        app.include_router(extra, prefix="/api")
    return app


def client(with_weekly_plan: bool = False) -> TestClient:
    return TestClient(make_app(with_weekly_plan))


def add_child(c: TestClient, age_group: str = "7-9", birth_month: Optional[str] = None,
              gender: Optional[str] = None, device: str = DEVICE, name: str = "أحمد") -> int:
    body = {"name": name, "age_group": age_group}
    if birth_month is not None:
        body["birth_month"] = birth_month
    if gender is not None:
        body["gender"] = gender
    r = c.post("/api/children", json=body, headers={"X-Test-Device": device})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def add_child_row(age_group: str, device: str = DEVICE, birth_month: Optional[str] = None,
                  gender: Optional[str] = None) -> int:
    """A profile written straight to the table — for labels the API no longer
    accepts but production still holds (the legacy "0-3")."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO child_profiles (device_id, name, age_group, gender, birth_month) "
            "VALUES (?, 'طفل', ?, ?, ?)", (device, age_group, gender, birth_month))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def child_headers(child_id: int, device: str = DEVICE) -> dict[str, str]:
    token = child_token.issue_child_token(device, child_id, ttl_seconds=1800)
    return {"Authorization": f"Child-Bearer {token}"}


def freeze(monkeypatch, iso: str) -> datetime:
    """Pin the programs' clock to a UTC instant."""
    moment = datetime.fromisoformat(iso)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(pc, "_utcnow", lambda: moment)
    return moment


def rows(table: str, where: str = "1=1", params: tuple = ()) -> list[dict]:
    conn = get_conn()
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE {where}", params)]
    finally:
        conn.close()
