# AeroTrace — Rules for Claude Code (read this every session)

AeroTrace is our Honeywell Devils Invent (PS 1.1) project: a read-only, evidence-first
tool that turns a legacy C avionics repo into a source-linked graph, explains it with a
tightly limited LLM, and produces change-impact reports that humans review.

**Design rule (never break it):**
Static analysis builds the facts. The graph stores the facts. The LLM only explains facts
it is handed. Humans approve.

Before doing anything, read:
1. `docs/CONTRACTS.md` — the shared data shapes and entry points. This is the law.
2. `docs/DESIGN.md` — the full design. P0 scope only unless your prompt says otherwise.
3. Your stream's doc in `docs/streams/` (if it exists yet).

---

## 1. Team and file ownership

Four people, four streams. **You only edit files inside your stream's paths.**

| Stream | Who | Paths you may edit |
| --- | --- | --- |
| `analysis` | Person 1 | `aerotrace/ingest/`, `aerotrace/analysis/`, `demo/fixture/`, `demo/expected/`, `tests/analysis/`, `requirements/analysis.txt`, `docs/streams/analysis.md`, `docs/progress/analysis.md`, `docs/requests/from-analysis.md` |
| `graph` | Person 2 | `aerotrace/graph/`, `aerotrace/impact/`, `tests/graph/`, `requirements/graph.txt`, `docs/streams/graph.md`, `docs/progress/graph.md`, `docs/requests/from-graph.md` |
| `narrative` | Person 3 | `aerotrace/context/`, `aerotrace/narrative/`, `aerotrace/validators/`, `aerotrace/llm/`, `aerotrace/ask/`, `tests/narrative/`, `requirements/narrative.txt`, `docs/streams/narrative.md`, `docs/progress/narrative.md`, `docs/requests/from-narrative.md` |
| `app` | Person 4 | `aerotrace/service.py`, `aerotrace/api/`, `aerotrace/cli.py`, `aerotrace/review/`, `ui/`, `tests/e2e/`, `scripts/`, `Makefile`, `README.md`, `.github/`, `requirements/app.txt`, `docs/DEMO.md`, `docs/streams/app.md`, `docs/progress/app.md`, `docs/requests/from-app.md` |
| **LOCKED** | nobody (see §5) | `aerotrace/contracts/`, `docs/CONTRACTS.md`, `CLAUDE.md`, `.claude/`, `pyproject.toml`, `requirements.txt`, `requirements/base.txt`, `docs/DESIGN.md` |

Every `__init__.py` was created in the scaffold. Only the owner of a folder edits its `__init__.py`.

## 2. Hard rules

1. **Never edit a file outside your paths.** If you need something from another stream,
   write it in `docs/requests/from-<your-stream>.md` (what, why, by when), then tell the human
   so they can ping that teammate. Keep working with the fake meanwhile.
2. **Cross-stream calls only go through the entry points listed in `docs/CONTRACTS.md`**
   and the types in `aerotrace/contracts/`. Never import another stream's private modules.
3. **Until a real implementation is merged, use `aerotrace/contracts/fakes.py`.**
   Every stream must be runnable and testable on its own from minute one.
4. Never run code from the analyzed repo. Never use `shell=True`. Never let the LLM write
   SQL or Cypher. Never let the LLM create graph edges.
5. Python 3.11, full type hints, Pydantic v2 models from `aerotrace.contracts`, `ruff` clean,
   `pytest` tests for every public function.
6. No secrets in code. Read from `.env`: `ANTHROPIC_API_KEY`, `AEROTRACE_LLM_PROVIDER`
   (`disabled` | `anthropic`), `AEROTRACE_LLM_MODEL`, `AEROTRACE_DB` (default `.aerotrace/aerotrace.db`).
7. User-facing text must never say: "safe", "certified", "compliant", "no impact".
8. Add new dependencies only to **your** `requirements/<stream>.txt`. Never touch `requirements.txt`.

## 3. Git workflow (this is how we avoid merge conflicts)

**One branch per task.** Name it `<stream>/<short-task>`, e.g. `analysis/clang-adapter`.

**Start every task:**
```bash
git checkout main
git pull --ff-only
git checkout -b <stream>/<short-task>
```

**Commit small and often.** After each working step:
```bash
git add <only files inside your paths>      # NEVER `git add .` or `git add -A`
git commit -m "[<stream>] <what changed>"
```

**When you MUST push ("ship"):** whichever comes first:
- a task marked `🚢 SHIP` in your prompt is done;
- 90 minutes since your last push;
- before a merge cutoff (§4);
- before you take a break, eat, or sleep.

**Ship routine (do every step, in order):**
1. `make check` → must be green (ruff + pytest). If red: fix it. Never ship red.
2. `git fetch origin && git rebase origin/main`
3. Conflict in a file you own → resolve it. Conflict in a file you don't own →
   `git rebase --abort`, stop, and tell the human. Do not "fix" someone else's file.
4. `make check` again (other people's code just came in).
5. Update docs (§6) and commit them.
6. `git push -u origin HEAD`
7. `gh pr create --base main --title "[<stream>] <summary>" --body "<what changed / how tested / docs updated>"`
8. Wait for the CI check. If it's green **and** the PR only touches your paths:
   `gh pr merge --squash --delete-branch`.
   If it touches anything LOCKED: don't merge. Tell the human; it needs team approval.
9. `git checkout main && git pull --ff-only` and start the next task on a new branch.

Never push to `main` directly. Never force-push `main`. Never merge someone else's PR
without them saying yes.

## 4. Merge cutoffs (event schedule)

| When | What must be merged to `main` |
| --- | --- |
| Sat 12:30 PM | Everything for Status Report #1 (fixture → graph → call tree) |
| Sat 6:30 PM | Everything for Status Report #2 (impact result with evidence) |
| Sun 8:00 AM | **Feature freeze.** After this, bug fixes only. |
| Sun 10:30 AM | Final merge. Person 4 tags `v1.0-demo`. |
| Sun 11:00 AM | All work stops (event rule). |

## 5. Changing a contract (only if truly blocked)

1. Write the proposal in `docs/requests/from-<your-stream>.md`.
2. Tell the human; they agree it with the team out loud.
3. **Person 4** makes the change in a single PR titled `[contracts] ...`.
4. Changes must be **additive** (new optional fields, new entry points). Never rename or remove.
5. Right after it merges, everyone runs the "sync" shortcut.

## 6. Documentation (part of every PR)

- `docs/streams/<stream>.md` — what your module does, its public entry points, how to run it,
  current limits. Keep it true, not long.
- `docs/progress/<stream>.md` — append one line per merged PR:
  `- [Sat 14:05] merged clang adapter: calls + reads work; MAY_CALL next`
- Every public function gets a docstring (what it does, inputs, outputs, failure behavior).

## 7. Shortcuts the human may type

- **"sync"** → ship routine steps 2–4 only.
- **"ship it"** → full ship routine (§3).
- **"status"** → compare my prompt's task list with what's merged; say what's done, what's next,
  and any blockers.
- Slash commands also exist: `/ship` and `/sync`.

## 8. Repo layout

```
aerotrace/
  contracts/   models.py  repository.py  ids.py  fakes.py  sample_ncm.json   (LOCKED)
  ingest/      analysis/                                                      (analysis)
  graph/       impact/                                                        (graph)
  context/     narrative/  validators/  llm/  ask/                            (narrative)
  service.py   api/  cli.py  review/                                          (app)
ui/                                                                           (app)
demo/fixture/  demo/expected/                                                 (analysis)
tests/analysis/ tests/graph/ tests/narrative/ tests/e2e/
docs/ CONTRACTS.md DESIGN.md DEMO.md streams/ progress/ requests/
requirements.txt  requirements/{base,analysis,graph,narrative,app}.txt
```
