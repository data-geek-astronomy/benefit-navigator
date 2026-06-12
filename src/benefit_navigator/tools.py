"""Tool definitions exposed to Claude, plus a dispatcher to execute them.

The agent gets two tools:

  * `screen_benefits`  — runs the deterministic rules engine on a structured
    household. This is how the model gets eligibility results; it is told never
    to compute them itself.
  * `get_program_details` — looks up the plain-language description, apply URL,
    and next steps for a single program.

Tool input schemas are hand-written JSON Schema so the model has a clear,
stable contract for what to extract from the conversation.
"""

from __future__ import annotations

from typing import Any

from .models import KNOWN_ENROLLMENTS, KNOWN_FLAGS, Household
from .rules import load_knowledge_base, screen

TOOLS: list[dict[str, Any]] = [
    {
        "name": "screen_benefits",
        "description": (
            "Screen a household against all known benefit programs and return "
            "an eligibility result for each. Call this once you have the "
            "household size and (ideally) monthly income. It is safe to call "
            "with partial information — programs that need more data are marked "
            "'needs_more_info'. Always use this tool for eligibility; never "
            "estimate eligibility yourself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "household_size": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Total number of people in the household, including children.",
                },
                "monthly_income": {
                    "type": ["number", "null"],
                    "description": (
                        "Gross (before-tax) monthly household income in US dollars. "
                        "Use null if unknown. If the person gives an annual or weekly "
                        "figure, convert to monthly first."
                    ),
                },
                "state": {
                    "type": ["string", "null"],
                    "description": "Two-letter US state code, if known (e.g. 'CA').",
                },
                "enrolled_programs": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(KNOWN_ENROLLMENTS)},
                    "description": "Benefit programs the household is ALREADY enrolled in.",
                },
                "flags": {
                    "type": "object",
                    "description": "Yes/no situational facts about the household.",
                    "properties": {flag: {"type": "boolean"} for flag in KNOWN_FLAGS},
                    "additionalProperties": False,
                },
            },
            "required": ["household_size"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_program_details",
        "description": (
            "Look up the description, how-to-apply URL, and next steps for a "
            "single benefit program by its id."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "program_id": {
                    "type": "string",
                    "description": "The program id, e.g. 'snap', 'medicaid', 'wic'.",
                }
            },
            "required": ["program_id"],
            "additionalProperties": False,
        },
    },
]


def _run_screen_benefits(tool_input: dict[str, Any]) -> dict[str, Any]:
    household = Household(
        household_size=int(tool_input["household_size"]),
        monthly_income=tool_input.get("monthly_income"),
        state=tool_input.get("state"),
        enrolled_programs=tool_input.get("enrolled_programs", []) or [],
        flags=tool_input.get("flags", {}) or {},
    )
    return screen(household).to_dict()


def _run_get_program_details(tool_input: dict[str, Any]) -> dict[str, Any]:
    kb = load_knowledge_base()
    program_id = str(tool_input["program_id"]).lower().strip()
    for program in kb["programs"]:
        if program["id"] == program_id:
            return {
                "program_id": program["id"],
                "name": program["name"],
                "category": program.get("category", ""),
                "description": " ".join(program.get("description", "").split()),
                "income_limit_pct_fpl": program["income_limit_pct_fpl"],
                "apply_url": program.get("apply_url", ""),
                "next_steps": " ".join(program.get("next_steps", "").split()),
            }
    available = ", ".join(p["id"] for p in kb["programs"])
    return {"error": f"Unknown program '{program_id}'. Available: {available}."}


_DISPATCH = {
    "screen_benefits": _run_screen_benefits,
    "get_program_details": _run_get_program_details,
}


def run_tool(name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name. Returns a JSON-serializable dict."""
    handler = _DISPATCH.get(name)
    if handler is None:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return handler(tool_input)
    except Exception as exc:  # surface errors to the model so it can recover
        return {"error": f"{type(exc).__name__}: {exc}"}
