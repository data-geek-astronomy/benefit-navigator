# Runbook & Handoff Guide

This is the document for **whoever owns Benefit Navigator after the person who
built it is gone.** It assumes you are comfortable editing a text file and
running a couple of commands, but are not necessarily a software engineer. If
something here doesn't make sense, that's a bug in this document — please fix it.

---

## 1. What this thing is (in one paragraph)

Benefit Navigator is a chat assistant. A person describes their household; it
tells them which benefit programs they might qualify for and how to apply. It
does **not** make official decisions. The "brain" that decides eligibility is a
plain-English rules file you can edit (`knowledge_base/programs.yaml`). The chat
part is powered by Claude (Anthropic's AI) and needs an API key to run.

---

## 2. Running it

```bash
source .venv/bin/activate            # activate the Python environment
export ANTHROPIC_API_KEY=sk-ant-...  # the key (keep it secret; never commit it)
make app                             # opens the chat at http://localhost:8501
```

To stop it, press `Ctrl-C` in the terminal.

If `make app` fails with "command not found", run
`pip install -r requirements.txt` first.

---

## 3. The most common task: updating program rules

**You do not need a developer for this.** Open
`knowledge_base/programs.yaml` in any text editor.

Each program looks like this:

```yaml
  - id: snap
    name: "SNAP (Supplemental Nutrition Assistance Program)"
    category: "Food"
    description: >
      Monthly benefits to help buy groceries, loaded onto an EBT card.
    income_limit_pct_fpl: 130          # ← the income limit, as a % of poverty level
    categorical_shortcuts: ["tanf", "ssi"]
    apply_url: "https://www.fns.usda.gov/snap/state-directory"
    next_steps: >
      Apply through your state SNAP office...
```

Common edits:

| You want to… | Change this |
|---|---|
| Raise/lower an income limit | `income_limit_pct_fpl` |
| Fix the "how to apply" link | `apply_url` |
| Reword what the program is | `description` / `next_steps` |
| Update the yearly poverty numbers (do this every January) | the `fpl:` block at the top |
| Add a brand-new program | copy a whole `- id:` block, change the values |

**After ANY edit, always run the safety check:**

```bash
make test     # confirms the rules engine still works
make evals    # confirms the example scenarios still come out right
```

If both say everything passed, commit your change:

```bash
git add knowledge_base/programs.yaml
git commit -m "Update SNAP income limit for 2026"
git push
```

If a test **fails** after your edit, it usually means a scenario in
`evals/eval_cases.yaml` now expects a different outcome. Either your edit was
wrong, or the expected outcome needs updating too. When in doubt, undo your
edit (`git checkout knowledge_base/programs.yaml`) and ask for help.

> ⚠️ The numbers shipped in this repo are **examples**. Before real use, have a
> program expert confirm every limit against the actual agency rules.

---

## 4. Changing the AI's tone or rules of conduct

The assistant's personality and safety rules live in
`src/benefit_navigator/prompts.py`. This is plain English. You can adjust the
tone, reading level, or add a rule (e.g., "always mention the food bank
hotline"). After editing, run `make evals-live` (needs the API key) to confirm
the assistant still behaves — the built-in judge will catch unsafe changes like
the assistant guessing eligibility.

---

## 5. Cost control

Every chat costs a small amount of money (Anthropic charges per use). Knobs, set
in `.env`:

- `BENEFIT_NAV_MODEL=claude-sonnet-4-6` — switch to a cheaper, slightly less
  capable model. Re-run `make evals-live` after switching to confirm quality.
- `BENEFIT_NAV_EFFORT=low` — makes the AI think less (cheaper, faster).
- `BENEFIT_NAV_MAX_TOOL_ITERS=6` — a hard ceiling on AI steps per message so a
  bug can't run up a bill.

Watch spend in the Anthropic Console (console.anthropic.com → Usage). Set a
monthly budget alert there.

---

## 6. When something breaks

| Symptom | Likely cause | Fix |
|---|---|---|
| "Set the ANTHROPIC_API_KEY…" warning | Key not set | `export ANTHROPIC_API_KEY=...` |
| Chat hangs or errors | Anthropic outage or bad key | Check status.anthropic.com; verify the key |
| Wrong eligibility result | A rule in `programs.yaml` | Check the number; run `make evals` |
| `make test` fails | A code or rule change broke something | `git status` to see what changed; revert if unsure |
| Streamlit won't start | Missing packages | `pip install -r requirements.txt` |

---

## 7. The "watch someone break it" handoff checklist

Before declaring this handed off, sit with the new owner and have **them** do
each of these while you watch (don't do it for them):

- [ ] Start the app and complete one full screening conversation.
- [ ] Change an income limit in `programs.yaml`, run `make test` + `make evals`,
      and see a result change in the app.
- [ ] Break it on purpose (set a limit to a word instead of a number), watch the
      test fail, and revert with `git checkout`.
- [ ] Find their monthly spend in the Anthropic Console.
- [ ] Know who to contact when they're stuck.

When they can do all five without you touching the keyboard, the handoff is real.

---

## 8. Key facts to keep somewhere safe

- **Anthropic API key:** stored in `.env` (and in your secrets manager). Rotate
  it in the Anthropic Console if it ever leaks.
- **Repo:** `<your-git-remote-url>`
- **Owner / escalation contact:** `<name, email>`
- **Annual task:** update the `fpl:` block in `programs.yaml` each January when
  new poverty guidelines publish.
