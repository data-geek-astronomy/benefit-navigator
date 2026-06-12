"""Runtime configuration, read from environment variables.

Keeps model id and tuning knobs in one place so the program team can change
behavior via `.env` (see `.env.example`) without editing code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # claude-opus-4-8 is the most capable model; for a high-volume, cost-
    # sensitive nonprofit deployment you can set BENEFIT_NAV_MODEL to
    # claude-sonnet-4-6 in .env to trade a little capability for lower cost.
    model: str = os.getenv("BENEFIT_NAV_MODEL", "claude-opus-4-8")
    # Effort controls how much the model thinks/acts. "medium" is a good
    # balance for this conversational screening task.
    effort: str = os.getenv("BENEFIT_NAV_EFFORT", "medium")
    max_tokens: int = int(os.getenv("BENEFIT_NAV_MAX_TOKENS", "4096"))
    # Safety valve so a buggy loop can't spin forever / run up cost.
    max_tool_iterations: int = int(os.getenv("BENEFIT_NAV_MAX_TOOL_ITERS", "6"))


settings = Settings()
