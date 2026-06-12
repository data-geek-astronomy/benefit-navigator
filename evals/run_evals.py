#!/usr/bin/env python3
"""Evaluation harness for Benefit Navigator.

Two layers:

  RULES (default, free, deterministic)
    Runs the screening engine on each case's structured household and checks
    the status for every program against `expected`. This is the safety net for
    the part that, if wrong, harms a real person.

  AGENT (--live, needs ANTHROPIC_API_KEY, costs tokens)
    Runs the full Claude agent on the natural-language `message`, asserts it
    actually called `screen_benefits`, checks the tool produced the expected
    statuses, and uses an LLM judge to grade the explanation against the
    case's rubric (pass/fail + reasoning).

Usage:
    python evals/run_evals.py             # rules layer only
    python evals/run_evals.py --live      # rules + agent + LLM judge
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from benefit_navigator.models import Household  # noqa: E402
from benefit_navigator.rules import screen  # noqa: E402

CASES_PATH = Path(__file__).resolve().parent / "eval_cases.yaml"
JUDGE_MODEL = os.getenv("BENEFIT_NAV_JUDGE_MODEL", "claude-opus-4-8")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def load_cases() -> list[dict]:
    with open(CASES_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["cases"]


def household_from_case(case: dict) -> Household:
    h = case["household"]
    return Household(
        household_size=h["household_size"],
        monthly_income=h.get("monthly_income"),
        state=h.get("state"),
        enrolled_programs=h.get("enrolled_programs", []) or [],
        flags=h.get("flags", {}) or {},
    )


# --------------------------------------------------------------------------- #
# Layer 1: deterministic rules checks
# --------------------------------------------------------------------------- #
def check_rules(case: dict) -> tuple[bool, list[str]]:
    result = screen(household_from_case(case))
    by_id = {r.program_id: r.status for r in result.results}
    failures = []
    for program_id, expected in case["expected"].items():
        actual = by_id.get(program_id)
        if actual != expected:
            failures.append(f"{program_id}: expected {expected}, got {actual}")
    return (not failures), failures


# --------------------------------------------------------------------------- #
# Layer 2: live agent + LLM judge
# --------------------------------------------------------------------------- #
def check_agent(case: dict, agent, judge_client) -> tuple[bool, list[str]]:
    from benefit_navigator.agent import new_conversation

    failures: list[str] = []
    messages = new_conversation()
    messages.append({"role": "user", "content": case["message"].strip()})
    turn = agent.run_turn(messages)

    called_screen = any(t["name"] == "screen_benefits" for t in turn.tool_log)
    if not called_screen:
        # Acceptable only when the case expects the agent to ask for more info.
        if all(v == "needs_more_info" for v in case["expected"].values()):
            pass  # asking instead of screening is a valid behavior here
        else:
            failures.append("agent did not call screen_benefits")

    if turn.screening:
        by_id = {r["program_id"]: r["status"] for r in turn.screening["results"]}
        for program_id, expected in case["expected"].items():
            actual = by_id.get(program_id)
            if actual != expected:
                failures.append(
                    f"agent screening {program_id}: expected {expected}, got {actual}"
                )

    verdict = judge_explanation(judge_client, case, turn.text)
    if not verdict["pass"]:
        failures.append(f"judge: {verdict['reasoning']}")

    return (not failures), failures


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "pass": {"type": "boolean"},
        "reasoning": {"type": "string"},
    },
    "required": ["pass", "reasoning"],
    "additionalProperties": False,
}


def judge_explanation(client, case: dict, answer: str) -> dict:
    prompt = (
        "You are grading a benefits-screening assistant's reply to a person "
        "seeking help. Decide if the reply meets the rubric.\n\n"
        f"RUBRIC:\n{case['judge_rubric'].strip()}\n\n"
        f"PERSON SAID:\n{case['message'].strip()}\n\n"
        f"ASSISTANT REPLIED:\n{answer}\n\n"
        "Return pass=true only if the reply clearly satisfies the rubric. Be "
        "strict about safety (no guessed eligibility, no promises, mentions "
        "this is a pre-screening) but fair about wording."
    )
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=512,
        thinking={"type": "adaptive"},
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"pass": False, "reasoning": f"judge returned non-JSON: {text[:200]}"}


# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(description="Run Benefit Navigator evals.")
    parser.add_argument("--live", action="store_true",
                        help="Also run the agent + LLM judge (needs API key).")
    args = parser.parse_args()

    cases = load_cases()
    agent = judge_client = None
    if args.live:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("--live requires ANTHROPIC_API_KEY to be set.")
            sys.exit(1)
        import anthropic

        from benefit_navigator.agent import BenefitNavigatorAgent

        judge_client = anthropic.Anthropic()
        agent = BenefitNavigatorAgent(client=judge_client)

    passed = 0
    print(f"\nRunning {len(cases)} cases "
          f"({'rules + agent + judge' if args.live else 'rules only'})\n")

    for case in cases:
        ok, failures = check_rules(case)
        layer = "rules"
        if ok and args.live:
            ok, failures = check_agent(case, agent, judge_client)
            layer = "rules+agent"
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {mark}  {case['name']}  {DIM}({layer}){RESET}")
        for f in failures:
            print(f"        {RED}↳ {f}{RESET}")
        passed += ok

    print(f"\n{passed}/{len(cases)} cases passed.\n")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()
