"""Deterministic benefits screening engine.

This module is the trustworthy core of the system. It contains NO calls to an
LLM — given a `Household`, it produces the same `ScreeningResult` every time,
driven entirely by `knowledge_base/programs.yaml`. That auditability is the
whole point: the agent (agent.py) is responsible for the messy job of turning a
conversation into a `Household`, and this engine is responsible for the part
where being wrong actually harms someone.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import Household, ProgramResult, ScreeningResult

DEFAULT_KB_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "programs.yaml"
)


@lru_cache(maxsize=8)
def load_knowledge_base(path: str | Path = DEFAULT_KB_PATH) -> dict[str, Any]:
    """Load and lightly validate the program knowledge base."""
    with open(path, "r", encoding="utf-8") as fh:
        kb = yaml.safe_load(fh)

    if "fpl" not in kb or "programs" not in kb:
        raise ValueError("Knowledge base must define 'fpl' and 'programs'.")
    for program in kb["programs"]:
        for required in ("id", "name", "income_limit_pct_fpl"):
            if required not in program:
                raise ValueError(
                    f"Program {program.get('id', '?')} missing '{required}'"
                )
    return kb


def monthly_fpl(household_size: int, fpl: dict[str, Any]) -> float:
    """Federal Poverty Level expressed as a monthly dollar figure."""
    annual = fpl["base_annual"] + (household_size - 1) * fpl["per_additional_person"]
    return annual / 12.0


def _evaluate_program(
    household: Household, program: dict[str, Any], fpl: dict[str, Any], band_pct: float
) -> ProgramResult:
    name = program["name"]
    category = program.get("category", "Other")
    next_steps = " ".join(program.get("next_steps", "").split())
    apply_url = program.get("apply_url", "")

    def result(status: str, reason: str) -> ProgramResult:
        return ProgramResult(
            program_id=program["id"],
            program_name=name,
            category=category,
            status=status,
            reason=reason,
            next_steps=next_steps,
            apply_url=apply_url,
        )

    # 1) Required situational conditions are a HARD gate (e.g., WIC requires a
    #    pregnancy or a child under 5). This is checked first so that a
    #    categorical income shortcut can never wave someone past a condition
    #    they fundamentally don't meet.
    required_any = program.get("required_conditions_any")
    if required_any:
        if not any(household.has_flag(c) for c in required_any):
            readable = " or ".join(c.replace("_", " ") for c in required_any)
            return result(
                "not_eligible",
                f"This program requires the applicant to be {readable}, which "
                f"does not appear to apply to this household.",
            )

    # 2) Categorical shortcut: already enrolled in a qualifying program waives
    #    the income test (but not the required conditions checked above).
    shortcuts = set(program.get("categorical_shortcuts", []))
    matched = shortcuts.intersection(household.enrolled_programs)
    if matched:
        via = ", ".join(sorted(matched)).upper()
        return result(
            "likely_eligible",
            f"Likely qualifies automatically because the household is already "
            f"enrolled in {via} (categorical eligibility).",
        )

    # 3) Income test.
    if household.monthly_income is None:
        return result(
            "needs_more_info",
            "Monthly household income is needed to check this program.",
        )

    threshold = monthly_fpl(household.household_size, fpl) * (
        program["income_limit_pct_fpl"] / 100.0
    )
    income = household.monthly_income
    pct_of_limit = program["income_limit_pct_fpl"]

    if income <= threshold:
        return result(
            "likely_eligible",
            f"Income of ${income:,.0f}/mo is within the limit of "
            f"${threshold:,.0f}/mo ({pct_of_limit}% of the Federal Poverty Level "
            f"for a household of {household.household_size}).",
        )

    if income <= threshold * (1 + band_pct / 100.0):
        return result(
            "possibly_eligible",
            f"Income of ${income:,.0f}/mo is just above the limit of "
            f"${threshold:,.0f}/mo. Deductions (housing, childcare, medical) can "
            f"lower countable income, so it is worth applying to confirm.",
        )

    return result(
        "not_eligible",
        f"Income of ${income:,.0f}/mo is above the limit of ${threshold:,.0f}/mo "
        f"({pct_of_limit}% of the Federal Poverty Level for a household of "
        f"{household.household_size}).",
    )


def screen(household: Household, kb: dict[str, Any] | None = None) -> ScreeningResult:
    """Screen a household against every program in the knowledge base."""
    kb = kb or load_knowledge_base()
    band = float(kb.get("borderline_band_pct", 10))
    results = [
        _evaluate_program(household, program, kb["fpl"], band)
        for program in kb["programs"]
    ]
    return ScreeningResult(household=household, results=results)
