# AeroTrace — Build Phases (all four people work in parallel in every phase)

**How to read this:** the prototype is built in 6 phases. Inside each phase every person has their own
**unit** (a small milestone in their own folders), so nobody waits on anybody and nobody edits the same file.
At the end of each phase there is a **GATE**: a 10-minute check where everyone has merged, pulled, and the
team proves the phase works on `main`. **Nobody starts the next phase until the gate passes.**

Unit names: `<phase>.<person>` — e.g. unit **2.3** = Phase 2, Person 3. "Prompt" = which step to paste from
your prompts file (`01_PERSON1…`, `02_PERSON2…`, `03_PERSON3…`, `04_PERSON4…`).

## The big picture

| Phase | Name | Rough time | What exists at the gate | Event checkpoint |
| --- | --- | --- | --- | --- |
| 0 | Foundation | Fri night | Repo, contracts, fakes, demo C code, database core, context builder, service layer | — |
| 1 | First slice | Sat 9 AM – 12:30 | Real code → graph → call tree, shown in the UI | **Status Report #1 (1 PM)** |
| 2 | Impact and trust checks | Sat 1 – 6:30 PM | All 6 outputs, validators, impact with evidence, unresolved calls, review buttons | **Status Report #2 (7 PM)** |
| 3 | AI and staleness | Sat 7 PM – late | LLM explanations, Ask box, STALE after a code edit, CLI/API | — |
| 4 | Harden | Overnight – Sun 8 AM | Failure paths, speed, extras, demo script, backups | **Feature freeze 8 AM** |
| 5 | Freeze and rehearse | Sun 8 – 11 AM | Bug fixes only, 3 rehearsals, tag `v1.0-demo` | **Work stops 11 AM** |

---

## Rules that keep four people from colliding (apply to every phase)

1. **Own folders only** (table in `CLAUDE.md` §1). A unit never needs a file from another person's folder.
2. **Talk through contracts.** Cross-person calls go only through the entry points in `docs/CONTRACTS.md`.
   Until the real one is merged, use the fake in `aerotrace/contracts/fakes.py`.
3. **Contracts are frozen inside a phase.** Changes are additive, made by Person 4 in one `[contracts]` PR,
   and only at a gate, so everyone syncs once.
4. **One branch per unit step, `/ship` when it's done,** and at least every 90 minutes.
5. **Spare units:** if you finish early, take the first unfinished item from your "If done early" line. Never
   take something from a teammate's folder; ask them.
6. **Falling behind?** Use the "Cut if behind" line for that phase. Cut the extra, never the gate.

---

## PHASE 0 — Foundation (Friday night)

Goal: everyone can build and test on their own from the first minute.

| Unit | Person | Build | Prompt | Done when |
| --- | --- | --- | --- | --- |
| **0.1** | Person 1 | Demo C fixture with every planted case, hand-written oracle, safe scanner + run manifest, libclang go/no-go (max 2 hours) | Steps 2, 3, 4, 5 | Fixture and oracle merged; scanner tests green; Clang decision written in `docs/streams/analysis.md` |
| **0.2** | Person 2 | SQLite schema, load/activate, all read methods (`find_symbols`, edges, evidence) | Steps 2, 3 | `open_repository` returns the real repo; sample loads, activates, reads back equal |
| **0.3** | Person 3 | Context builder (smallest useful facts + allowed evidence ids + secret redaction) | Step 2 | Bundle for `NavMsg_IsValid` has callers/callees and matching allowed ids |
| **0.4** | Person 4 | Repo scaffold, contracts, fakes, CI, then the service layer | S1–S5 | `make check` green on `main`; service functions pass tests on the fakes |

**GATE 0 checklist**
- [ ] The two open PRs are merged: `[contracts]` (blank-query `find_symbols` **and** `run_id` includes a digest of scanned file contents), then `[app] service layer`.
- [ ] Everyone: `git pull`, `make install`, `make check` green.
- [ ] `demo/fixture/` and `demo/expected/oracle.json` are on `main`.
- [ ] Clang or Tree-sitter decision is written down and the team knows it.
- [ ] `gh` works on all four laptops (`gh auth status`).

**If done early:** P1 → Step 6 start. P2 → Step 4 start. P3 → Step 3 start. P4 → S6 start.
**Cut if behind:** skip the Clang spike result detail; just choose Tree-sitter.

---

## PHASE 1 — First slice: real code → graph → call tree (Sat 9 AM – 12:30 PM)

Goal: one real path works end to end and you can see it in the UI. Builds on Phase 0's fixture, database,
context builder and service.

| Unit | Person | Build | Prompt | Done when |
| --- | --- | --- | --- | --- |
| **1.1** | Person 1 | Tree-sitter adapter + parser manager (per-file fallback), then the full Normalized Code Model with evidence spans, then `run_analysis` wired (replaces the stub). Plus the Clang adapter if the decision was GO | Steps 6, 7 (+8) | Direct-call precision and recall ≥ 95% against the oracle; every edge has evidence; missing header in gaps; broken file never crashes the run |
| **1.2** | Person 2 | Bounded traversal with full paths, cycle safety, stable order, truncation flag. If Person 1 has already merged `run_analysis`, also run the real-fixture graph test (Step 6) | Step 4 (+6) | Traversal tests green: cycles, depth/node limits, same order five runs in a row |
| **1.3** | Person 3 | Templates for **function card** and **call tree** (solid / dashed "possible" / red unresolved), classification rules, sanitized Mermaid; `generate_artifact(use_llm=False)` works for both | Step 3 | Every claim cites allowed evidence; Mermaid has no forbidden content |
| **1.4** | Person 4 | Streamlit UI: Overview, Explorer + Ask box, Impact page (shell), Review page (read-only); badges and "Open evidence" source viewer; advisory banner everywhere | S6 | `make ui` launches; call tree renders; clicking a claim shows exact lines (or an honest "uses sample data" message) |

**Dependencies:** 1.3 and 1.4 start on fakes and switch to real once 1.1 and 1.2 merge. Nobody waits.

**GATE 1 checklist (before 12:30 PM, Status Report #1 at 1 PM)**
- [ ] `run_analysis` on `demo/fixture` returns a real model.
- [ ] Real model loads into the real SQLite repo and activates.
- [ ] UI shows the call tree for `NavMsg_IsValid` on real data (say so honestly if anything is still fake).
- [ ] `make check` green on `main`. Everyone synced.

**Demo line for Report #1:** "fixture → graph → call tree."
**If done early:** P1 → Step 9. P2 → Step 5. P3 → Step 4. P4 → S7.
**Cut if behind:** drop the Clang adapter; Tree-sitter only.

---

## PHASE 2 — Impact and trust checks (Sat 1 PM – 6:30 PM)

Goal: the heart of the demo. Impact analysis with evidence, honest uncertainty, all six outputs, and the review buttons.
Builds on Phase 1's real model, traversal and templates.

| Unit | Person | Build | Prompt | Done when |
| --- | --- | --- | --- | --- |
| **2.1** | Person 1 | Function pointers: static table → `MAY_CALL`, runtime pointer → `UNRESOLVED_CALL` + gap line; `variant` support (`NAV_VARIANT_B` changes the call and the `run_id`) | Step 9 | Oracle tests pass for all three; unresolved callback has an exact `file:line` |
| **2.2** | Person 2 | **Impact analysis** (direct / transitive / verification / uncertain frontier, full paths, fixed empty wording), then artifact/claim/review storage. Then the real-fixture check (Step 6) | Steps 5, 7, 6 | Direct recall ≥ 90%, precision ≥ 80%; the runtime callback is always in the frontier; query under 3 s; reviews table never loses a row |
| **2.3** | Person 3 | The other four templates (data flow, static sequence, module card, impact dossier), then the **validators** (reject whole artifact on bad evidence ids, banned words, proposed edges, unsafe Mermaid) | Steps 4, 5 | All six kinds work with the LLM off; every validator rule has a failing-case test |
| **2.4** | Person 4 | Review workflow (accept / edit / reject / investigate, append-only history), Impact page filled in, then the **end-to-end test** on the real fixture | S7, S8 | Review actions tested; e2e test runs (steps skipped with a clear message if a stream isn't merged) |

**Dependencies:** 2.3's impact dossier and 2.4's impact page use the fakes until 2.2 merges; 2.2 needs the
`READS/WRITES/CALLS` edges from 1.1 (already merged at Gate 1).

**GATE 2 checklist (before 6:30 PM, Status Report #2 at 7 PM)**
- [ ] Impact for `NavMsg_IsValid` on the real fixture shows four groups, each item with a hop-by-hop path and evidence.
- [ ] The runtime callback shows in "uncertain frontier" (the system refuses to guess).
- [ ] All six artifacts open from the UI.
- [ ] A fake LLM output citing a made-up evidence id is rejected and falls back to the template.
- [ ] Accept / edit / reject works and history is kept.

**Demo line for Report #2:** "impact result with evidence."
**If done early:** P1 → Step 10. P2 → Step 8. P3 → Step 6. P4 → S9.
**Cut if behind:** skip module card polish and the sequence diagram; keep function card, call tree, impact dossier.

---

## PHASE 3 — AI and staleness (Sat 7 PM – late)

Goal: add the "AI" the judges expect, plus the live STALE moment. Builds on Phase 2's validators, claims and review.

| Unit | Person | Build | Prompt | Done when |
| --- | --- | --- | --- | --- |
| **3.1** | Person 1 | Re-analysis stability: identical IDs on re-run, a one-line edit changes only the touched evidence, `run_id` includes file-content digest even with no git commit; `apply_demo_edit` / `revert_demo_edit` helpers. Clang adapter if still pending | Step 10 (+8) | Temp-copy test passes without a commit; helpers documented |
| **3.2** | Person 2 | **Staleness:** accepted/edited claims whose cited hash changed become STALE; history kept; never auto-approved. Then `export_subgraph` for the UI graph view | Step 8 (+9a) | Accept → edit one cited line → STALE; untouched claims stay accepted |
| **3.3** | Person 3 | **LLM provider + grounded enrichment** (template first, validate, fall back), then the **Ask box** with typed tools only | Steps 6, 7 | Mock-provider tests pass; Ask answers the stale-nav question with evidence; LLM off still works |
| **3.4** | Person 4 | CLI (`doctor`, `analyze`, `summarize`, `impact`, `coverage`, `ask`), thin FastAPI, STALE highlight in the UI, `make demo` | S9 | `make demo` runs from a fresh DB to a launched UI |

**GATE 3 checklist (the full demo, rehearsed once)**
- [ ] Run → function card → click a claim → exact source lines.
- [ ] Impact → frontier → accept a claim → apply the edit → reanalyze → **STALE**.
- [ ] Whole flow works with `AEROTRACE_LLM_PROVIDER=disabled` **and** with the LLM on.
- [ ] No claim anywhere says "safe", "certified", "compliant", or "no impact".

**If done early:** go to your Phase 4 unit.
**Cut if behind:** drop `export_subgraph` and the API; keep CLI minimal (`analyze`, `impact`).

---

## PHASE 4 — Harden (overnight → Sunday 8 AM)

Goal: make what exists hard to break, and make the demo repeatable. No new big features.

| Unit | Person | Build | Prompt | Done when |
| --- | --- | --- | --- | --- |
| **4.1** | Person 1 | Fixture and parser robustness tests; then stretch: study kit and the pinned NASA cFS scale run (real numbers only) | Step 11 | Parser never crashes on odd inputs; any numbers reported are measured |
| **4.2** | Person 2 | Failure-path tests (DB interruption keeps old run, traversal limit gives partial result), timings, optional Neo4j mirror | Step 9 | Failure table behaviors in DESIGN §6 each have a test |
| **4.3** | Person 3 | Real-fixture narrative tests, prompt-injection and adversarial validator tests, optional lexical discovery for conceptual questions | Steps 8, 9 | The "Ignore previous instructions…" comment never changes output |
| **4.4** | Person 4 | `demo_reset.sh`, `docs/DEMO.md` (exact 5-minute click path + judge Q&A), one run offline, screenshots and a 2-minute recording | S10 | Anyone on the team can run the demo from `DEMO.md` |

**GATE 4 = FEATURE FREEZE (Sun 8 AM)**
- [ ] `main` green. Every person's docs and progress file is current.
- [ ] Demo works from a fresh clone: `make install`, `make demo`.
- [ ] Backup screenshots and recording exist.

**Cut if behind:** skip cFS, Neo4j, lexical discovery, study kit. Never skip `DEMO.md` or the backup recording.

---

## PHASE 5 — Freeze and rehearse (Sunday 8 – 11 AM)

| Who | Do |
| --- | --- |
| Everyone | Run the "final check" step in your prompts file; docs fixes only. Only bug-fix PRs, each reviewed by one other person |
| Person 4 | Runs the demo from `DEMO.md` while the team times it |
| Everyone | Rehearse the 5-minute pitch **three times**, then practice judge questions (DESIGN §11) |
| **10:30 AM** | Last merge. Person 4 runs S11 and tags `v1.0-demo`. Demo from the tag |
| **11:00 AM** | **All work stops. Submit.** |

---

## Quick dependency map (what each phase needs from the one before)

```
Phase 0  fixture, oracle ─────────────▶ Phase 1  real parsing
Phase 0  database core ───────────────▶ Phase 1  traversal
Phase 0  context builder ─────────────▶ Phase 1  templates ─▶ Phase 2  more templates, validators
Phase 0  service layer ───────────────▶ Phase 1  UI ─────────▶ Phase 2  review, e2e ─▶ Phase 3  CLI/API
Phase 1  real model + traversal ──────▶ Phase 2  impact ─────▶ Phase 3  staleness
Phase 2  validators + claims ─────────▶ Phase 3  LLM, Ask
Phase 2  callbacks + variants ────────▶ Phase 3  re-analysis stability ─▶ Phase 4  demo script
```
