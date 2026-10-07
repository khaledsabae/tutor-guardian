"""Primary evidence and review holds for the authored lesson 11 source fix."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LESSON = "lesson_7-9_aqeedah_fundamentals_11"
UNIT = "aqe-who-created-allah-source-01"
PROOF = ROOT / "ops/data/deepen_paths/lesson11.source-proof.json"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _tool(name):
    sys.path.insert(0, str(ROOT / "ops/tools"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops/tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("number", [2713, 3276])
def test_primary_quote_matches_number_and_rejects_wrong_number(number):
    proof = _read(PROOF)
    source = next(s for s in proof["sources"] if s["local_number"] == number)
    unit = _read(ROOT / f"knowledge_base/units/{UNIT}.json")
    quote = source["quote_ar"]
    assert quote in unit["text_original"]
    assert hashlib.sha256(quote.encode()).hexdigest() == source["quote_sha256"]
    guard = _tool("check_hadith_citations")
    books = guard._load_index()["books"]
    assert guard.check_one(books, quote, f"صحيح {source['book']} — حديث {number}") is None
    assert guard.check_one(books, quote, f"صحيح {source['book']} — حديث 1") is not None


def test_primary_proof_cannot_silently_change_the_canon():
    proof = _read(PROOF)
    assert hashlib.sha256((ROOT / proof["canon_path"]).read_bytes()).hexdigest() == proof["canon_sha256"]
    assert proof["approval"]["human_approval"] is None
    assert proof["approval"]["model_review_performed"] is False


def test_source_fix_is_pending_and_bound_to_the_current_pair():
    ar = _read(ROOT / f"knowledge_base/curriculum/lessons/{LESSON}.json")
    en = _read(ROOT / f"knowledge_base/curriculum/i18n/en/lessons/{LESSON}.json")
    assert ar["unit_ids"] == en["unit_ids"] == [UNIT]
    for doc in (ar, en):
        assert doc["approved_by"] is None
        assert doc["translation"]["needs_scholar_review"] is True
        assert doc["translation"]["content_provenance"]["parenting_guidance"] == "app_authored"
        assert not doc["translation"].get("auto_review")
    parity = _tool("review_en_parity")
    fields = parity._field_pairs(ar, en, parity.CURRICULUM_FIELDS["lessons"])
    queue = _read(ROOT / "ops/data/en_parity_queue.json")["units"][LESSON]
    assert queue["category"] == "awaiting-review"
    assert queue["content_sha256"] == parity.content_sha(fields)
    assert "عقله يعمل ويبحث" not in ar["summary"]
    assert "التشبيه يزيد الحيرة" not in ar["summary"]
    assert "means their mind is working" not in en["summary"]
    assert "likening only increases confusion" not in en["summary"]
