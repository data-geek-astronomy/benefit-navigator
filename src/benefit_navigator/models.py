"""Typed data structures shared across the screening engine, tools, and UI."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# The set of yes/no situational flags the screener understands. Keeping these
# named in one place lets the tool schema, the rules engine, and the tests stay
# in sync. Add a flag here and reference it in programs.yaml to extend coverage.
KNOWN_FLAGS = (
    "pregnant_or_postpartum",
    "has_child_under_5",
    "has_dependent_children",
    "is_disabled",
    "is_senior_62_plus",
    "is_veteran",
)

# Programs a household may already be enrolled in (drives categorical shortcuts).
KNOWN_ENROLLMENTS = ("snap", "medicaid", "tanf", "ssi", "wic", "liheap")


@dataclass
class Household:
    """A normalized snapshot of a household's situation for screening.

    `monthly_income` is gross monthly household income in dollars. `None` means
    "not yet known" — the engine reports `needs_more_info` rather than guessing.
    """

    household_size: int
    monthly_income: Optional[float] = None
    state: Optional[str] = None
    enrolled_programs: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.household_size < 1:
            raise ValueError("household_size must be at least 1")
        self.enrolled_programs = [p.lower().strip() for p in self.enrolled_programs]
        # Drop unknown flags rather than silently trusting arbitrary input.
        self.flags = {k: bool(v) for k, v in self.flags.items() if k in KNOWN_FLAGS}

    def has_flag(self, name: str) -> bool:
        return bool(self.flags.get(name, False))


@dataclass
class ProgramResult:
    """The screening outcome for a single program."""

    program_id: str
    program_name: str
    category: str
    status: str  # likely_eligible | possibly_eligible | not_eligible | needs_more_info
    reason: str
    next_steps: str = ""
    apply_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScreeningResult:
    """The full result of screening a household against all programs."""

    household: Household
    results: list[ProgramResult]

    @property
    def likely(self) -> list[ProgramResult]:
        return [r for r in self.results if r.status == "likely_eligible"]

    @property
    def possibly(self) -> list[ProgramResult]:
        return [r for r in self.results if r.status == "possibly_eligible"]

    def to_dict(self) -> dict:
        return {
            "household": asdict(self.household),
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "likely_eligible": [r.program_id for r in self.likely],
                "possibly_eligible": [r.program_id for r in self.possibly],
            },
        }
