# Evaluation

A benefits screener's worst failure isn't a clunky sentence — it's a confident
*wrong* answer that sends someone down the wrong path. So we evaluate at two
levels, cheapest and most important first.

## Layer 1 — Rules evals (default)

```bash
python evals/run_evals.py      # or: make evals
```

Runs the deterministic engine (`rules.screen`) on each scenario in
`eval_cases.yaml` and asserts the eligibility status for **every program**
against `expected`. No API key, no cost, runs in CI on every push. This is the
guardrail on the part that can actually harm someone.

## Layer 2 — Agent evals + LLM judge (`--live`)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python evals/run_evals.py --live      # or: make evals-live
```

For each case this:

1. Runs the **real Claude agent** on the natural-language `message`.
2. Asserts the agent actually **called the `screen_benefits` tool** (it must
   never answer eligibility from memory). The exception: cases where every
   expected status is `needs_more_info` — there, asking a follow-up question
   instead of screening is correct behavior.
3. Checks the agent's screening matches the expected statuses.
4. Has an **LLM judge** (structured-output pass/fail + reasoning) grade the
   explanation against the case's `judge_rubric`: plain language, no guessed
   eligibility, no promises, states it's a pre-screening, gives a next step.

## Adding a case

Copy a block in `eval_cases.yaml`:

```yaml
  - name: "short_descriptive_name"
    message: >
      What the person types, in their own words.
    household:                      # the structured truth for the rules layer
      household_size: 3
      monthly_income: 2000
      flags: { has_child_under_5: true }
    expected:                       # status per program id (must match programs.yaml)
      snap: likely_eligible
      wic: likely_eligible
      # ...
    judge_rubric: >
      What a good plain-language reply must contain.
```

Keep `expected` in sync with `knowledge_base/programs.yaml`. If you change a
threshold there, the rules evals will tell you which expectations to update.

## Where these come from

The scenarios are modeled on real intake patterns: a single low-income adult, a
working family just over the SNAP line, someone already on SNAP (categorical
eligibility), and someone who doesn't know their income. As caseworkers flag
wrong screens in production, each becomes a new eval case — that feedback loop
is how the rules file earns trust over time.
