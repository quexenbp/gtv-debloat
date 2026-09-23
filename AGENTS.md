# Agent Guidelines — gtv-debloat

## Task delegation & model selection

When executing a multi-task plan, dispatch a **separate, fresh agent per task**
(one task = one agent, no shared context between them).

Choose the model by escalation — start cheap, climb only when confidence is low:

1. **Haiku first.** Use `haiku` as the default for each task.
2. **Escalate to Sonnet if Haiku is not confident** — if the task needs
   integration reasoning, multi-file coordination, or Haiku is unsure/blocked,
   redispatch on `sonnet`.
3. **Escalate to Opus 5.5 if Sonnet is not confident** — if Sonnet is still
   unsure, blocked, or the task needs real design judgment, redispatch on
   `opus` (Opus 5.5).

**Bias toward safety over cost.** If in doubt about correctness — especially on
anything touching the safety invariants below — go up a tier rather than ship a
guess. A wrong result on this tool can affect a real user's TV.

Reviews follow the same ladder: scale the reviewer model to the diff's risk and
size; use the most capable model for the final whole-branch review.

## Safety invariants (never weaken)

- Never `pm uninstall` / `adb uninstall` — disable only (`pm disable-user
  --user 0`), reversible with `pm enable`.
- Whitelisted/critical system packages must never be selectable or disabled
  (filtered in `selectable_packages` AND re-checked in `disable_packages`).
- Uncatalogued ("unknown" risk) packages require explicit `yes` confirmation.

## Project conventions

- Python 3.9+, standard library only at runtime. `pytest` is dev-only.
- Tests mock `adb`/`subprocess` — never invoke a real device in tests.
- On this machine `python` is a broken Windows Store stub; use
  `C:\Users\rogsr\AppData\Local\Programs\Python\Python312\python.exe`.
