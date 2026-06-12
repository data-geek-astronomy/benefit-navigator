# 🧭 Benefit Navigator

**An AI assistant that helps people find out which public benefits they may qualify for — in plain language, in about two minutes.**

Built for the kind of community nonprofit where a handful of caseworkers field hundreds of "what am I eligible for?" questions a month. A client (or a caseworker on their behalf) describes their household in ordinary words; Benefit Navigator asks a few follow-ups, screens them against programs like SNAP, Medicaid, WIC, LIHEAP, and Lifeline, and explains the results at a 6th-grade reading level with a clear next step.

> ⚠️ **It is a *pre-screening* tool, not an eligibility decision.** The agency that runs each program makes the final call. The assistant says so, every time, and never promises a benefit.

---

## Why it's built the way it is

The hard part of a benefits tool isn't the chat — it's *being right*, because a confident wrong answer sends a struggling family down the wrong path. So the architecture splits the work in two:

| Layer | Who does it | Why |
|---|---|---|
| **Understand the person** — turn a messy conversation into structured facts (household size, income, situation) | **Claude** (the agent) | Language is exactly what an LLM is good at. |
| **Decide eligibility** — apply the income thresholds and rules | **A deterministic engine** (`rules.py`, driven by a YAML file) | Eligibility must be auditable and identical every time. The model is told never to compute it itself — it *calls a tool*. |

That separation is the whole design. It means the part that can hurt someone is testable without an API key, and a non-technical program manager can update a threshold by editing one YAML file.

```
You: there's four of us, two little kids, we make about $3,500 a month

Benefit Navigator:
  Based on what you shared, here's what's worth pursuing:

  ✅ Likely a good fit
   • WIC — food and nutrition help for your young child
   • Medicaid — health coverage for the family
   • LIHEAP — help with heating/cooling bills

  🟡 Worth applying anyway
   • SNAP (food) — you're just over the income line, but things like
     rent and childcare can lower what counts. Applying is free.

  👉 Start with WIC: call your local clinic to set up a visit.

  This is a pre-screening, not a decision — the programs make the final call.
```

---

## Quickstart

```bash
git clone <your-fork-url> benefit-navigator && cd benefit-navigator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# The deterministic core needs no API key — prove it works first:
make test        # unit tests for the rules engine + tools
make evals       # scenario evals against expected outcomes

# To use the chat, set your key:
export ANTHROPIC_API_KEY=sk-ant-...     # or cp .env.example .env and edit
make app         # Streamlit UI at http://localhost:8501
make cli         # or a terminal chat
```

---

## What's in here

```
benefit-navigator/
├── src/benefit_navigator/
│   ├── rules.py          # deterministic screening engine (the trustworthy core)
│   ├── models.py         # Household / ProgramResult / ScreeningResult
│   ├── tools.py          # the two tools Claude can call + dispatcher
│   ├── agent.py          # manual Claude tool-use loop
│   ├── prompts.py        # system prompt (judgment + safety rules)
│   └── config.py         # model + tuning knobs, read from env
├── knowledge_base/
│   └── programs.yaml     # ← program rules a non-technical owner edits
├── app/streamlit_app.py  # staff-facing chat UI
├── cli.py                # terminal chat
├── evals/
│   ├── eval_cases.yaml   # scenarios + expected outcomes + judge rubrics
│   └── run_evals.py      # 2-layer harness (rules; + agent & LLM judge w/ --live)
├── tests/                # pytest unit tests (no API key)
├── data/sample_intake.json
├── ARCHITECTURE.md       # how it fits together + design decisions
└── RUNBOOK.md            # operations + handoff guide for whoever owns it next
```

---

## Evaluation

Being wrong is the failure mode that matters, so correctness is tested at two levels (details in [`evals/README.md`](evals/README.md)):

1. **Rules evals** (free, deterministic) — run the engine on each scenario and assert the eligibility status for every program. These are the guardrail on the dangerous part.
2. **Agent evals** (`make evals-live`) — run the full Claude agent on the natural-language prompt, confirm it actually used the screening tool, and have an **LLM judge** grade the explanation against a rubric (plain language, no guessed eligibility, mentions it's a pre-screening, gives a next step).

---

## Built with

- **Claude** (`claude-opus-4-8`) via the Anthropic Python SDK — adaptive thinking, tool use, and structured outputs for the judge.
- Python, PyYAML, Streamlit, pytest.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for design decisions and [`RUNBOOK.md`](RUNBOOK.md) for the handoff guide.

## Disclaimer

The program rules and income figures in `knowledge_base/programs.yaml` are **illustrative simplifications** for demonstration. They are not legal advice and not a guarantee of eligibility. Before any real-world use, confirm current rules with each administering agency and have the knowledge base reviewed by program staff.
