"""Mixed-size actual responses may prove exact current fields, never a fake cache."""

import importlib.util
import json
import sys
from pathlib import Path
import pytest


@pytest.fixture
def rp():
    s = importlib.util.spec_from_file_location(
        "rp_proof", Path(__file__).resolve().parents[2] / "ops/tools/review_en_parity.py"
    )
    m = importlib.util.module_from_spec(s)
    sys.modules[s.name] = m
    s.loader.exec_module(m)
    return m


def example(rp):
    item = rp.Item(
        "adhkar",
        "adhkar:family_adhkar",
        Path("en.json"),
        Path("ar.json"),
        {
            "items[0].text": {"ar": "نصيحة", "en": "Tip"},
            "items[0].source": {"ar": "مصدر", "en": "Source"},
        },
    )
    fragments = []
    for model in ("deepseek-v4-pro", "glm-5.2"):
        fields = dict(item.fields)
        cid = "tip-0"
        fragments.append(
            {
                "model": model,
                "id": cid,
                "batch_ids": [cid],
                "fields": fields,
                "content_sha256": rp.content_sha(fields),
                "raw": json.dumps({"items": [{"id": cid, "defects": []}]}),
            }
        )
    return item, {
        "key": item.key,
        "content_sha256": item.sha,
        "prompt_version": rp.PROMPT_V,
        "responses": fragments,
    }


def test_complete_actual_fragment_proof_has_no_missing_family(rp, monkeypatch):
    item, proof = example(rp)
    monkeypatch.setattr(rp, "deterministic_defects", lambda item: [])
    v = rp.replay_proof(item, ("deepseek-v4-pro", "glm-5.2"), proof)
    assert v.unreviewed == [] and v.blocking([]) == []


def test_malformed_defect_cannot_disappear_into_approval(rp, monkeypatch):
    item, proof = example(rp)
    monkeypatch.setattr(rp, "deterministic_defects", lambda item: [])
    proof["responses"][0]["raw"] = json.dumps(
        {"items": [{"id": "tip-0", "defects": ["invalid defect record"]}]}
    )
    with pytest.raises(ValueError):
        rp.replay_proof(item, ("deepseek-v4-pro", "glm-5.2"), proof)


@pytest.mark.parametrize("reviewers", [
    ("deepseek-v4-pro", "deepseek-v4-pro"),
    ("deepseek-v4-pro", "deepseek-v3"),
    ("deepseek-v4-pro", "unidentified-model"),
])
def test_two_distinct_known_families_required(rp, monkeypatch, reviewers):
    item, proof = example(rp)
    monkeypatch.setattr(rp, "deterministic_defects", lambda item: [])
    proof["responses"][1]["model"] = reviewers[1]
    with pytest.raises(ValueError):
        rp.replay_proof(item, reviewers, proof)


@pytest.mark.parametrize("reviewers", [
    ("deepseek-v4-pro", "deepseek-v4-pro"),
    ("deepseek-v4-pro", "deepseek-v3"),
])
def test_invalid_reviewers_cannot_start_a_run(rp, monkeypatch, reviewers):
    from types import SimpleNamespace

    def unexpected_access():
        raise AssertionError("Invalid reviewer configuration reached review state")

    monkeypatch.setattr(rp, "load_adjudications", unexpected_access)
    with pytest.raises(ValueError):
        rp.run([], SimpleNamespace(reviewer_a=reviewers[0], reviewer_b=reviewers[1]))


def test_changed_field_cannot_reuse_old_raw_judgment(rp, monkeypatch):
    item, proof = example(rp)
    monkeypatch.setattr(rp, "deterministic_defects", lambda item: [])
    old = proof["responses"][1]
    old["fields"] = {**old["fields"], "items[0].text": {"ar": "نصيحة", "en": "Older wording"}}
    old["content_sha256"] = rp.content_sha(old["fields"])
    v = rp.replay_proof(item, ("deepseek-v4-pro", "glm-5.2"), proof)
    assert v.unreviewed == ["glm-5.2"]


@pytest.mark.parametrize("bad", ["sha", "prompt", "raw", "missing_id", "bad_defects"])
def test_bad_provenance_or_incomplete_raw_cannot_approve(rp, monkeypatch, bad):
    item, proof = example(rp)
    monkeypatch.setattr(rp, "deterministic_defects", lambda item: [])
    if bad == "sha":
        proof["responses"][0]["content_sha256"] = "fake"
    if bad == "prompt":
        proof["prompt_version"] = "old"
    if bad == "raw":
        proof["responses"][0]["raw"] = "{invalid"
    if bad == "missing_id":
        proof["responses"][0]["raw"] = '{"items":[]}'
    if bad == "bad_defects":
        proof["responses"][0]["raw"] = '{"items":[{"id":"tip-0","defects":null}]}'
    with pytest.raises(ValueError):
        rp.replay_proof(item, ("deepseek-v4-pro", "glm-5.2"), proof)


def test_actual_medium_findings_survive_replay(rp, monkeypatch):
    item, proof = example(rp)
    monkeypatch.setattr(rp, "deterministic_defects", lambda item: [])
    proof["responses"][0]["raw"] = json.dumps(
        {
            "items": [
                {
                    "id": "tip-0",
                    "defects": [
                        {"field": "items[0].text", "severity": "medium", "why": "Meaning changed"}
                    ],
                }
            ]
        }
    )
    assert len(rp.replay_proof(item, ("deepseek-v4-pro", "glm-5.2"), proof).blocking([])) == 1


def test_pack_fingerprint_is_required(rp):
    item, proof = example(rp)
    proof["content_sha256"] = "stale"
    with pytest.raises(ValueError):
        rp.replay_proof(item, ("deepseek-v4-pro", "glm-5.2"), proof)
