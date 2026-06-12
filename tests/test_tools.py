"""Tests for the tool dispatch layer the agent calls into (no API key needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benefit_navigator.tools import TOOLS, run_tool


def test_tool_schemas_are_well_formed():
    names = {t["name"] for t in TOOLS}
    assert names == {"screen_benefits", "get_program_details"}
    for tool in TOOLS:
        assert tool["input_schema"]["type"] == "object"
        assert "required" in tool["input_schema"]


def test_screen_benefits_tool_returns_summary():
    out = run_tool("screen_benefits", {"household_size": 1, "monthly_income": 1200})
    assert "summary" in out
    assert "snap" in out["summary"]["likely_eligible"]
    assert len(out["results"]) == 5


def test_screen_benefits_handles_partial_input():
    out = run_tool("screen_benefits", {"household_size": 2})
    statuses = {r["program_id"]: r["status"] for r in out["results"]}
    assert statuses["snap"] == "needs_more_info"


def test_get_program_details_known_and_unknown():
    ok = run_tool("get_program_details", {"program_id": "snap"})
    assert ok["name"].startswith("SNAP")
    assert ok["apply_url"]

    bad = run_tool("get_program_details", {"program_id": "nope"})
    assert "error" in bad


def test_unknown_tool_is_handled_gracefully():
    assert "error" in run_tool("does_not_exist", {})


def test_bad_input_is_reported_not_raised():
    # household_size 0 raises inside Household; dispatcher should catch it.
    out = run_tool("screen_benefits", {"household_size": 0})
    assert "error" in out
