"""P6 (PR #26 review): the story feature sent the child's name to the model.

On a cache miss the live prompt said «بطل القصة طفل اسمه «يوسف»». It now names
the canonical hero of the right gender and the child's name is put in after
generation — the same path the cached stories already took.
"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient


class _Gateway:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return SimpleNamespace(text="رحلة سارة\nكانت سارة تحب الصدق.\nالدرس المستفاد: الصدق نجاة.")


def test_the_story_prompt_carries_no_child_name(monkeypatch):
    from app.main import app
    from app.services import ai_gateway, story_service
    gw = _Gateway()
    monkeypatch.setattr(ai_gateway, "get_gateway", lambda: gw)
    monkeypatch.setattr(story_service, "get_cached_story", lambda *a, **k: None)
    with TestClient(app) as client:
        tok = client.post("/api/chat/sessions", json={"device_id": "dev-story"}).json()["token"]
        r = client.post("/api/program/story", headers={"Authorization": f"Bearer {tok}"},
                        json={"child_name": "فاطمة", "age_group": "4-6", "theme": "honesty"})
    assert r.status_code == 200, r.text
    assert gw.prompts and "فاطمة" not in gw.prompts[0]
    assert "سارة" in gw.prompts[0]                    # the hero, gendered from «فاطمة»
    assert "فاطمة" in r.json()["story"] and "سارة" not in r.json()["story"]


def test_gender_guess_is_local_and_simple():
    from app.services.story_service import guess_gender
    assert guess_gender("فاطمة") == guess_gender("ليلى") == guess_gender("مريم") == "female"
    assert guess_gender("يوسف") == guess_gender("أحمد") == "male"
