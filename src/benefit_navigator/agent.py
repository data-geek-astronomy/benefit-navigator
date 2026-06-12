"""The Benefit Navigator agent: a manual Claude tool-use loop.

We use a manual agentic loop (rather than the SDK tool runner) on purpose: it
keeps the dependency surface small, makes the control flow auditable for a
team that will own this after handoff, and gives us a clean place to capture
the structured screening result the conversation produced.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic

from .config import settings
from .prompts import SYSTEM_PROMPT
from .tools import TOOLS, run_tool


@dataclass
class AgentTurn:
    """The result of one user turn: the reply text plus anything structured."""

    text: str
    screening: Optional[dict[str, Any]] = None  # last screen_benefits result
    tool_log: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)  # updated history


class BenefitNavigatorAgent:
    """Stateless-per-call agent. Pass the running message history in and out."""

    def __init__(self, client: Optional[anthropic.Anthropic] = None) -> None:
        # Anthropic() reads ANTHROPIC_API_KEY (or an `ant auth login` profile)
        # from the environment.
        self.client = client or anthropic.Anthropic()
        # Whether to send adaptive thinking + effort. If the configured model or
        # the installed SDK rejects those, we degrade to a plain request once and
        # stay degraded for the rest of the process (see _create_message).
        self._rich_request = True

    def _create_message(self, messages: list[dict[str, Any]]):
        """Call the Messages API, gracefully degrading on a bad-request error.

        Some models/accounts don't accept `thinking: adaptive` or
        `output_config.effort`. Rather than crash the whole app, we drop those
        optional params and retry once so screening still works.
        """
        base = dict(
            model=settings.model,
            max_tokens=settings.max_tokens,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        if self._rich_request:
            try:
                return self.client.messages.create(
                    **base,
                    thinking={"type": "adaptive"},
                    output_config={"effort": settings.effort},
                )
            except anthropic.BadRequestError:
                self._rich_request = False  # degrade for the rest of the session
        return self.client.messages.create(**base)

    def run_turn(self, messages: list[dict[str, Any]]) -> AgentTurn:
        """Advance the conversation by one user turn.

        `messages` is the full history in Anthropic message format. The user's
        new message should already be appended before calling this. Returns an
        AgentTurn whose `.messages` is the updated history to reuse next turn.
        """
        screening: Optional[dict[str, Any]] = None
        tool_log: list[dict[str, Any]] = []

        for _ in range(settings.max_tool_iterations):
            response = self._create_message(messages)

            # Preserve the full assistant content (including thinking + tool_use
            # blocks) — required for a valid follow-up request.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                text = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                return AgentTurn(
                    text=text,
                    screening=screening,
                    tool_log=tool_log,
                    messages=messages,
                )

            # Execute every tool call in this turn and feed results back.
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                output = run_tool(block.name, block.input)
                tool_log.append(
                    {"name": block.name, "input": block.input, "output": output}
                )
                if block.name == "screen_benefits" and "error" not in output:
                    screening = output
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output),
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        # Iteration cap hit — return a safe message rather than looping forever.
        return AgentTurn(
            text=(
                "I'm having trouble completing that. Could you rephrase, or share "
                "the household size and monthly income so I can screen directly?"
            ),
            screening=screening,
            tool_log=tool_log,
            messages=messages,
        )


def new_conversation() -> list[dict[str, Any]]:
    """Return a fresh, empty message history."""
    return []
