#!/usr/bin/env python3
"""Command-line chat for Benefit Navigator.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python cli.py

Type your messages; the assistant replies. Type 'quit' to exit. After any
screening, a compact results table is printed alongside the reply.
"""

from __future__ import annotations

import sys

# Make `src/` importable without installing the package.
sys.path.insert(0, __file__.rsplit("/", 1)[0] + "/src")

from benefit_navigator.agent import BenefitNavigatorAgent, new_conversation  # noqa: E402

STATUS_LABEL = {
    "likely_eligible": "LIKELY",
    "possibly_eligible": "WORTH A TRY",
    "needs_more_info": "NEED INFO",
    "not_eligible": "no",
}


def print_screening(screening: dict) -> None:
    print("\n  ── Screening results " + "─" * 40)
    for r in screening["results"]:
        label = STATUS_LABEL.get(r["status"], r["status"])
        print(f"  [{label:>11}]  {r['program_name']}")
    print("  " + "─" * 60 + "\n")


def main() -> None:
    try:
        agent = BenefitNavigatorAgent()
    except Exception as exc:  # almost always a missing API key
        print(f"Could not start agent: {exc}")
        print("Set ANTHROPIC_API_KEY in your environment and try again.")
        sys.exit(1)

    messages = new_conversation()
    print("Benefit Navigator  (type 'quit' to exit)\n")
    print("Assistant: Hi! I can help you see which benefit programs you might "
          "qualify for. To start, how many people live in your household?\n")

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if user.lower() in {"quit", "exit", "q"}:
            print("Goodbye.")
            break
        if not user:
            continue

        messages.append({"role": "user", "content": user})
        turn = agent.run_turn(messages)
        messages = turn.messages

        print(f"\nAssistant: {turn.text}\n")
        if turn.screening:
            print_screening(turn.screening)


if __name__ == "__main__":
    main()
