"""Benefit Navigator — an AI benefits pre-screening assistant.

A Claude-powered agent that helps social-services staff and clients understand
which public benefit programs a household may qualify for, in plain language.

Design principle: Claude does NOT decide eligibility from memory. It extracts
structured facts from a natural-language conversation, then calls a
deterministic, auditable rules engine (`rules.screen`) to compute results. This
keeps determinations transparent and prevents the model from inventing rules.
"""

from .models import Household, ProgramResult, ScreeningResult
from .rules import load_knowledge_base, screen

__all__ = [
    "Household",
    "ProgramResult",
    "ScreeningResult",
    "load_knowledge_base",
    "screen",
]

__version__ = "0.1.0"
