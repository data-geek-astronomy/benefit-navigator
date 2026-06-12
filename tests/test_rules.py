"""Unit tests for the deterministic screening engine.

These run without an API key and cover the logic that must never be wrong:
income thresholds, the borderline band, hard categorical gates, and
categorical income shortcuts.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benefit_navigator.models import Household
from benefit_navigator.rules import load_knowledge_base, monthly_fpl, screen


def status_for(result, program_id):
    return {r.program_id: r.status for r in result.results}[program_id]


def test_monthly_fpl_matches_formula():
    fpl = load_knowledge_base()["fpl"]
    # 1-person 2024 FPL is $15,060/yr -> $1,255/mo.
    assert monthly_fpl(1, fpl) == pytest.approx(1255.0)
    # Each additional person adds $5,380/yr -> ~$448.33/mo.
    assert monthly_fpl(2, fpl) == pytest.approx((15060 + 5380) / 12)


def test_single_adult_low_income_qualifies_broadly():
    result = screen(Household(household_size=1, monthly_income=1200))
    assert status_for(result, "snap") == "likely_eligible"
    assert status_for(result, "medicaid") == "likely_eligible"
    assert status_for(result, "liheap") == "likely_eligible"
    assert status_for(result, "lifeline") == "likely_eligible"
    # No pregnancy / young child -> WIC is gated out.
    assert status_for(result, "wic") == "not_eligible"


def test_borderline_band_marks_possibly_eligible():
    # hh=4 SNAP limit = 2600 * 1.30 = 3380; 3500 is within +10% (3718).
    result = screen(Household(household_size=4, monthly_income=3500))
    assert status_for(result, "snap") == "possibly_eligible"


def test_income_far_over_limit_is_not_eligible():
    result = screen(Household(household_size=2, monthly_income=4000))
    assert status_for(result, "snap") == "not_eligible"
    assert status_for(result, "medicaid") == "not_eligible"


def test_categorical_shortcut_waives_income_test():
    # On SNAP already -> LIHEAP and Lifeline qualify categorically even at high income.
    result = screen(
        Household(household_size=2, monthly_income=4000, enrolled_programs=["snap"])
    )
    assert status_for(result, "liheap") == "likely_eligible"
    assert status_for(result, "lifeline") == "likely_eligible"


def test_required_condition_is_a_hard_gate_even_with_shortcut():
    # On SNAP but no pregnancy/young child -> WIC must still be not_eligible.
    result = screen(
        Household(household_size=2, monthly_income=1000, enrolled_programs=["snap"])
    )
    assert status_for(result, "wic") == "not_eligible"


def test_wic_qualifies_with_young_child():
    result = screen(
        Household(
            household_size=3,
            monthly_income=2000,
            flags={"has_child_under_5": True},
        )
    )
    assert status_for(result, "wic") == "likely_eligible"


def test_unknown_income_needs_more_info():
    result = screen(
        Household(household_size=3, monthly_income=None,
                  flags={"has_child_under_5": True})
    )
    assert status_for(result, "snap") == "needs_more_info"
    assert status_for(result, "wic") == "needs_more_info"


def test_household_size_must_be_positive():
    with pytest.raises(ValueError):
        Household(household_size=0)


def test_unknown_flags_are_dropped():
    h = Household(household_size=1, flags={"made_up_flag": True})
    assert "made_up_flag" not in h.flags
