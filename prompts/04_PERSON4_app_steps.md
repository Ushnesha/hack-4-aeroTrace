# PERSON 4 — App, UI, Integration — step-by-step prompts

You go FIRST (Steps S1-S3 set up the repo for everyone). Others wait for your "scaffold is on main".
Paste ONE step at a time. 🚢 = ends with a push.
You own: `aerotrace/service.py`, `aerotrace/api/`, `aerotrace/cli.py`, `aerotrace/review/`, `ui/`, `tests/e2e/`,
`scripts/`, `Makefile`, `README.md`, `.github/`, `requirements/app.txt`, `docs/DEMO.md`,
`docs/streams/app.md`, `docs/progress/app.md`, `docs/requests/from-app.md`.
You are also the only person who changes contracts (CLAUDE.md section 5).

Before S1: create the empty GitHub repo, add the 3 teammates as collaborators, clone it, copy the kit
files in (CLAUDE.md, START_HERE.md, docs/CONTRACTS.md, docs/DESIGN.md, .claude/commands/ship.md,
.claude/commands/sync.md, the prompts/ folder), and open Claude Code in it.

---

## S1 — Project files and folders (Fri night, ~10 min). Straight to main, only now.
````
Read CLAUDE.md, docs/CONTRACTS.md and docs/DESIGN.md. This is the ONLY time we commit straight to main.
Create:
1. pyproject.toml (package aerotrace, Python >=3.11, ruff line length 100, pytest testpaths=["tests"]).
2. requirements.txt containing exactly: -r requirements/base.txt, -r requirements/analysis.txt,
   -r requirements/graph.txt, -r requirements/narrative.txt, -r requirements/app.txt (one per line).
3. requirements/base.txt: pydantic>=2, python-dotenv, pytest, ruff. The other four requirements files:
   one comment line each.
4. .env.example: ANTHROPIC_API_KEY=, AEROTRACE_LLM_PROVIDER=disabled, AEROTRACE_LLM_MODEL=,
   AEROTRACE_DB=.aerotrace/aerotrace.db
5. .gitignore: Python defaults, .env, .aerotrace/, .venv/, __pycache__/, *.db
6. The folder layout from CLAUDE.md section 8, with __init__.py in every package under aerotrace/ and
   every tests/ subfolder, and .gitkeep in demo/fixture, demo/expected, ui, scripts.
7. Titled empty files: docs/streams/{analysis,graph,narrative,app}.md,
   docs/progress/{analysis,graph,narrative,app}.md, docs/requests/from-{analysis,graph,narrative,app}.md,
   docs/DEMO.md.
Do not commit yet. Tell me when done.
````

## S2 — Contracts and fakes (Fri night, ~25 min)
````
Implement docs/CONTRACTS.md EXACTLY in aerotrace/contracts/:
- models.py: all enums as Literal aliases and all models from sections 4-5.
- repository.py: the GraphRepository Protocol from section 6.
- ids.py: make_id(*parts) -> "sha256:" + hex of sha256 over "\x1f".join(parts); hash_bytes(b) -> same style.
- __init__.py re-exporting everything.
- scripts/make_sample_ncm.py that builds aerotrace/contracts/sample_ncm.json using make_id. The sample is
  a miniature of the demo scenario: functions NavTask_Run, NavMsg_Decode, NavMsg_IsValid,
  NavState_Update, Guidance_Step, Display_Refresh, Dispatch_Handle; a global g_nav_state with READS and
  WRITES; one MAY_CALL; one UNRESOLVED_CALL to an ExternalSymbol; one Test node with VERIFIES; one file
  FALLBACK_PARSED and one FAILED; build_context PARTIAL. Every edge's evidence_id must exist.
- fakes.py: fake_run_analysis, FakeGraphRepository (in-memory, full protocol, BFS bounded_traversal,
  real staleness by comparing snippet_hash between two runs), fake_compute_impact, fake_generate_artifact
  (template-only Artifact with 1-2 SUPPORTED claims citing real evidence), fake_answer.
- Stub entry points that call the fakes, each with "# TODO(<stream>): replace with real implementation":
  aerotrace/analysis/__init__.py -> run_analysis; aerotrace/graph/__init__.py -> open_repository;
  aerotrace/impact/__init__.py -> compute_impact; aerotrace/narrative/__init__.py -> generate_artifact;
  aerotrace/ask/__init__.py -> answer.
- tests/test_contracts.py: sample loads and validates, every edge's evidence exists, IDs stable across two
  builds, FakeGraphRepository traversal and staleness work.
Run it with pytest and fix failures. Tell me when green.
````

## S3 — Tooling, CI, README, publish (Fri night, ~10 min)
````
Add: Makefile targets install (create .venv and pip install -r requirements.txt), check (ruff check . then
pytest -q), fmt (ruff format .), demo (echo placeholder), ui (streamlit run ui/app.py placeholder).
Add .github/workflows/check.yml: on pull_request and push to main, Python 3.11, install, make check.
Write README.md: one-paragraph summary, the design rule, setup commands, the stream table from CLAUDE.md
section 1, and "read CLAUDE.md before contributing".
Run make install and make check; both must pass. Then git add everything, commit "[setup] scaffold,
contracts, fakes, CI", push to main. Then try to enable branch protection on main with gh (require PRs and
the check workflow); if you can't, tell me exactly where to click in GitHub settings.
Finally print a message I can paste to the team: "Scaffold is on main. Pull, run make install, copy
.env.example to .env, then paste your Step 1."
````

## S4 — Kickoff for the app stream (Fri night)
````
You are the APP stream and integration lead (Person 4). From now on we use branches and /ship.
Reply in 5 lines: my folders, what I deliver (service.py, review, UI, CLI/API, e2e test, demo, final tag),
the rule that the UI calls service.py directly, the cutoffs, and my step plan. Then wait.
````

## S5 — Service layer (Fri night / Sat early) 🚢
````
Branch: app/service.
Create aerotrace/service.py using ONLY the entry points in docs/CONTRACTS.md:
- analyze(repo_path, variant="baseline") -> RunManifest: run_analysis -> open_repository(AEROTRACE_DB from
  env) -> load_model -> activate.
- overview(run_id) -> dict: manifest, build-context state, counts of PARSED/FALLBACK_PARSED/FAILED/SKIPPED,
  unresolved-call count, known gaps.
- search(run_id, q), artifact(run_id, kind, subject_id, use_llm), impact(run_id, seed_ids),
  ask(run_id, question).
- evidence(run_id, evidence_id) -> {evidence, source_lines}: read the file from the analyzed repo, re-hash
  the exact byte span and FLAG a mismatch instead of showing drifted code.
- reanalyze(repo_path, variant) -> {new_run_id, stale_claim_ids}: analyze again, then
  mark_stale_for_changed_evidence(old, new).
Tests in tests/e2e/test_service.py using the stubs/fakes. Run make check, then /ship.
````

## S6 — Streamlit UI (Sat morning) 🚢 BEFORE 12:30 PM
````
Branch: app/ui.
Add streamlit (and networkx or pyvis if needed) to requirements/app.txt. Build ui/app.py and ui/pages/.
Show on EVERY page: "Engineering aid - not certification evidence. Advisory; requires independent
engineering review."
Pages: (1) Analysis Overview: commit, variant, build-context badge (PARTIAL in amber), coverage counts,
unresolved calls, gaps, run_id. (2) Code Explorer + Ask: symbol search, Ask box, function card, call tree
rendered from Mermaid, every claim with a classification badge (SUPPORTED green, INFERRED blue, ASSUMED
amber, UNKNOWN red outline, CONFLICTING red) and an "Open evidence" button showing exact source lines
with line numbers. (3) Impact Analysis: choose seed(s); four collapsible groups (Direct, Transitive,
Verification, Uncertain frontier); each item expands to its path hop by hop with evidence; truncation
banner. (4) Review Queue (read-only for now).
make ui must launch it. Run make check, then /ship. Status Report #1 = fixture -> graph -> call tree;
if real code is not merged yet, say honestly that the demo uses fakes.
````

## S7 — Review workflow (Sat afternoon) 🚢
````
Branch: app/review.
Create aerotrace/review/ with apply_review(repo, claim_id, action, reviewer, rationale=None, new_text=None):
ACCEPT -> status ACCEPTED; EDIT -> new revision with origin HUMAN, status EDITED, old text kept in the
review event; REJECT -> REJECTED; INVESTIGATE -> NEEDS_INVESTIGATION. Always append a ReviewEvent
(reviewer, timestamp, run_id, rationale); never delete history. Regenerated output is never auto-approved.
Wire it to the Review Queue page (groups by status, STALE highlighted at the top, reviewer name field).
Tests for every action and for history kept. Run make check, then /ship.
````

## S8 — Integration test on the real thing (Sat 4-6:30 PM) 🚢 BEFORE 6:30 PM
````
Branch: app/integration.
First "sync". Then read docs/requests/from-*.md and docs/progress/*.md and tell me the team status in 3
lines. Write tests/e2e/test_demo_flow.py on the REAL fixture (skip a step with a clear message if its
stream is not merged yet): analyze demo/fixture -> overview shows PARTIAL and one FAILED file ->
function_card for NavMsg_IsValid has claims with valid evidence -> impact for NavMsg_IsValid has a
non-empty uncertain_frontier -> accept a claim -> apply the demo edit to a temp copy (use
aerotrace.analysis.demo_edit if present) -> reanalyze -> that claim is STALE.
Fix integration problems in service.py and ui/. For problems in other streams, write the requests file and
tell me. Run make check, then /ship. Status Report #2 = impact result with evidence.
````

## S9 — CLI and thin API (Sat evening) 🚢
````
Branch: app/cli-api.
aerotrace/cli.py with Typer: doctor (Python, deps, libclang, DB path, LLM provider), analyze, summarize
<symbol>, impact <symbol>, coverage, ask "<question>". aerotrace/api/ with FastAPI under /api/v1:
GET /health, POST /runs, GET /runs/{id}, GET /runs/{id}/symbols,
GET /runs/{id}/artifacts/{kind}/{symbol_id}, POST /runs/{id}/impact, POST /runs/{id}/ask,
GET /runs/{id}/evidence/{eid}, POST /claims/{cid}/reviews. Every handler just calls service.py.
Add typer, fastapi, uvicorn to requirements/app.txt. Make "make demo" do: fresh DB -> analyze demo/fixture
-> print overview -> launch the UI. Run make check, then /ship.
````

## S10 — Demo script and backups (Sat night to Sun 8 AM) 🚢
````
Branch: app/demo.
1) scripts/demo_reset.sh: restore the fixture (undo the live edit) and rebuild the DB.
2) docs/DEMO.md: the exact 5-minute click path: overview -> function card -> click a claim -> source lines
   -> impact for the stale-nav change -> unresolved callback shown in the frontier ("refuses to guess") ->
   accept a claim -> apply the edit -> STALE -> measured results, limits, roadmap. Add answers to the
   likely judge questions from DESIGN section 11 and a 30-second fallback plan.
3) Run the whole demo once with AEROTRACE_LLM_PROVIDER=disabled (no network) and once with it on. Note any
   difference in docs/DEMO.md.
4) Tell me to take screenshots and a 2-minute screen recording as backup (keep large files out of git).
Run make check, then /ship.
````

## S11 — Freeze and tag (Sun 8 AM, then 10:30 AM)
````
At 8 AM: only bug-fix PRs from now. Run "status" and give me the 3-line team status.
At 10:30 AM: confirm main is green (make check), README.md has setup, make demo, architecture summary and
honest limits. Then: git checkout main && git pull --ff-only && git tag v1.0-demo && git push origin
v1.0-demo. We demo from that tag.
````
