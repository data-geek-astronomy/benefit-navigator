# Architecture

This document explains how Benefit Navigator is put together and *why* the
important decisions were made the way they were.

## The one decision that drives everything

**Claude understands the person; a deterministic engine decides eligibility.**

A large language model is excellent at turning "there's four of us and I bring
in about thirty-five hundred a month" into structured facts. It is the wrong
tool for *deciding* eligibility, because:

- eligibility must be **auditable** — a caseworker needs to know exactly why a
  result came out the way it did;
- it must be **reproducible** — the same household must always get the same
  answer;
- it must be **cheap to change** — when a poverty guideline updates in January,
  a program manager should fix a number, not a prompt.

So the model is given a tool, `screen_benefits`, and the system prompt forbids
it from ever stating eligibility on its own. All it can do is gather facts and
call the tool. The tool runs `rules.screen()`, which is pure Python with no
model in the loop.

```
                    ┌──────────────────────────────────────────┐
   user message ───▶│  BenefitNavigatorAgent  (agent.py)        │
                    │  Claude + manual tool-use loop            │
                    └───────────────┬──────────────────────────┘
                                    │ tool_use: screen_benefits(household)
                                    ▼
                    ┌──────────────────────────────────────────┐
                    │  run_tool()  (tools.py)                    │
                    │  builds a Household, calls screen()        │
                    └───────────────┬──────────────────────────┘
                                    ▼
                    ┌──────────────────────────────────────────┐
                    │  screen()  (rules.py)  ── DETERMINISTIC    │
                    │  reads knowledge_base/programs.yaml        │
                    │  returns ScreeningResult (per-program)     │
                    └───────────────┬──────────────────────────┘
                                    │ JSON tool_result
                                    ▼
                    Claude explains the result in plain language
```

## Components

| File | Responsibility |
|---|---|
| `models.py` | `Household`, `ProgramResult`, `ScreeningResult`. Normalizes/validates input (drops unknown flags, rejects bad household size). |
| `rules.py` | The screening engine. Loads the YAML knowledge base, computes monthly FPL, evaluates each program. **No LLM calls.** |
| `tools.py` | JSON-Schema tool definitions Claude sees, plus a dispatcher that executes them and always returns JSON-serializable dicts (errors included, so the model can recover). |
| `prompts.py` | The system prompt. Encodes the judgment/safety rules and the plain-language style. |
| `agent.py` | A manual tool-use loop. Captures the last screening result and a tool log for the UI. |
| `config.py` | Model id and tuning knobs, read from environment variables. |
| `app/`, `cli.py` | Two front ends over the same agent. |
| `evals/` | Two-layer evaluation (see below). |

## Why a manual tool-use loop (not the SDK tool runner)

The SDK's tool runner is great, but for a project that will be **handed off to a
small team**, an explicit loop wins:

- the control flow is readable top-to-bottom — no hidden iteration;
- it's the natural place to capture the structured `screening` result and a
  `tool_log` for display and debugging;
- it has a hard `max_tool_iterations` cap, so a misbehaving loop can't run up
  cost — important for a budget-constrained nonprofit.

The loop preserves the full assistant `content` (including thinking and
`tool_use` blocks) when appending to history, which is required for valid
follow-up requests.

## Model configuration

- **Model:** `claude-opus-4-8` by default (most capable). Switchable to
  `claude-sonnet-4-6` via `BENEFIT_NAV_MODEL` for a cheaper deployment.
- **Adaptive thinking** (`thinking: {type: "adaptive"}`) lets the model decide
  how much to reason per turn — most screening turns are simple, a few aren't.
- **Effort** defaults to `medium` (`output_config.effort`), a good
  cost/quality balance for a conversational task.
- The **LLM judge** in evals uses structured outputs
  (`output_config.format` with a JSON schema) so its pass/fail verdict parses
  reliably.

## The knowledge base (`programs.yaml`)

This is the system's most-edited file and is intentionally readable by
non-engineers. Each program declares an income limit as a percentage of the
Federal Poverty Level, optional hard conditions (`required_conditions_any`,
e.g. WIC needs a pregnancy or a child under 5), and optional categorical
shortcuts (being on SNAP can waive the income test for LIHEAP/Lifeline).

Evaluation order inside `rules.py` is deliberate:
1. **Required conditions** — a hard gate, checked first so a categorical
   shortcut can never wave someone past a condition they don't meet.
2. **Categorical shortcut** — waives the income test only.
3. **Income test** — within limit → likely; within the borderline band → worth
   a try; otherwise not eligible. Unknown income → needs more info.

## Two-layer evaluation

- **Rules layer:** deterministic, free, runs in CI. Asserts the per-program
  status for each scenario. This is the safety net for the part that can hurt
  someone.
- **Agent layer (`--live`):** runs the real agent, checks it *used the tool*
  and produced the expected statuses, then an LLM judge grades the explanation
  for safety and clarity.

## What I'd add next

- Per-state rule overlays (programs vary by state) layered on top of the
  federal baseline.
- A feedback loop where caseworkers flag a wrong screen, feeding new eval cases.
- Spanish-language support (the prompt and rubric already generalize; the
  knowledge base text would need translation).
- Logging/analytics on which programs get surfaced, to help the host org spot
  unmet need.
