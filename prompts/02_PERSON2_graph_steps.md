# PERSON 2 — Graph + Impact — step-by-step prompts

Setup (after Person 4 says "scaffold is on main"): `git checkout main && git pull && make install && cp .env.example .env`.
Open Claude Code. Paste ONE step at a time. 🚢 = ends with a push.
You own: `aerotrace/graph/`, `aerotrace/impact/`, `tests/graph/`, `requirements/graph.txt`,
`docs/streams/graph.md`, `docs/progress/graph.md`, `docs/requests/from-graph.md`.
Build and test on `aerotrace/contracts/sample_ncm.json` first. Use the real fixture once Person 1 merges.

---

## STEP 1 — Kickoff (Fri night)
````
You are the GRAPH stream of AeroTrace (Person 2). Read CLAUDE.md, docs/CONTRACTS.md and docs/DESIGN.md
sections 4.4, 4.5, 4.10, 4.11, 4.12. No code yet. Reply in 5 lines: folders I may edit, the two entry
points I deliver (aerotrace.graph.open_repository, aerotrace.impact.compute_impact), the GraphRepository
methods I must implement, git/push rules, and my step plan. Then wait.
````

## STEP 2 — SQLite schema, load, activate (Fri night / Sat early) 🚢
````
Branch: graph/sqlite-core.
Create aerotrace/graph/sqlite_repo.py with a class implementing the GraphRepository protocol in
aerotrace/contracts/repository.py. Use only the built-in sqlite3. ALL SQL is parameterized; no SQL is
ever built from user or LLM text.
Tables: runs (manifest JSON, status STAGED/ACTIVE/FAILED), nodes, edges, evidence, coverage, gaps,
artifacts, claims, reviews. Every row has run_id. Indexes on (run_id,source), (run_id,target),
(run_id,name). The reviews table is append-only: never UPDATE or DELETE it.
- load_model(ncm): one transaction, status STAGED; roll back on any error; return run_id.
- activate(run_id): validate first (edge endpoints exist, every evidence_id exists, every edge has at
  least one evidence). Valid -> ACTIVE. Invalid -> FAILED and the previously active run stays active.
- Implement get_manifest, get_coverage, get_known_gaps, active_run_id.
Replace the stub in aerotrace/graph/__init__.py: open_repository(db_path) creates the parent dir and
returns the real repo. Remove the TODO(graph) comment.
Tests (tests/graph/test_sqlite_core.py): load sample -> activate -> read back equal; a broken model
(edge to missing node) fails and the old active run stays; two runs never leak into each other.
Run make check, then /ship. Then tell me so I can tell Persons 3 and 4.
````

## STEP 3 — Read methods (Sat early) 🚢
````
Branch: graph/reads.
Implement get_node, find_symbols (case-insensitive match on name and qualified_name; rank exact >
prefix > contains; filter by kinds; limit), edges_from, edges_to (optional type filter), get_evidence.
All parameterized, all scoped by run_id.
Tests: ranking order, type filters, unknown ids return None or [], 100 symbols stay fast.
Document the public API in docs/streams/graph.md. Run make check, then /ship.
````

## STEP 4 — Bounded traversal (Sat morning) 🚢 BEFORE 12:30 PM
````
Branch: graph/traversal.
Implement bounded_traversal(run_id, seed_id, types, direction, limits) returning
(paths, truncated, truncation_reason). BFS that keeps the FULL path of PathHop (source, target,
edge_type, evidence_ids) to every reached node. Cycle-safe. Stable order: sort by edge type, then
target name, then id. Stop at max_depth, max_nodes, max_edges or timeout_s and set truncated=True with
the reason. Defaults: TraversalLimits().
Tests: cycles, depth limit, node limit, deterministic order across 5 runs, direction in vs out.
Run make check, then /ship. Tell me when merged (Status Report #1 needs it for the call tree).
````

## STEP 5 — Impact analysis (Sat afternoon) 🚢 BEFORE 6:30 PM
````
Branch: graph/impact.
In aerotrace/impact/ implement compute_impact exactly per docs/DESIGN.md 4.10:
1) resolve seeds inside one run; 2) DIRECT = reverse callers (CALLS in), readers/writers of what the
seed writes, the containing module; 3) TRANSITIVE = keep walking CALLS/READS/WRITES within limits;
4) VERIFICATION = Test nodes linked by VERIFIES to anything in the impact set; 5) UNCERTAIN_FRONTIER =
any path containing MAY_CALL, UNRESOLVED_CALL, evidence with quality FALLBACK_PARSED, or a file with
status FAILED (put it here, NOT in direct/transitive); 6) every item keeps its full path with per-hop
evidence; stable sort; report truncation; 7) nothing found -> empty_message with the exact wording from
DESIGN 4.10. Never say "no impact".
Replace the stub in aerotrace/impact/__init__.py.
Tests on the sample, then on demo/expected/oracle.json if Person 1's fixture is merged: direct recall
>= 90%, precision >= 80%, the runtime callback always lands in the frontier, query < 3 s.
Run make check, then /ship. Tell me when merged (Status Report #2).
````

## STEP 6 — Switch to the real fixture (Sat afternoon, when Person 1 has merged run_analysis) 🚢
````
Branch: graph/real-fixture.
Add tests/graph/test_real_fixture.py that runs aerotrace.analysis.run_analysis on demo/fixture,
loads it into a temp SQLite repo, activates it and checks: NavMsg_IsValid is findable, its callers
match the oracle, impact for seed NavMsg_IsValid matches the oracle groups, the unresolved callback is
in uncertain_frontier. Fix any mismatch ON MY SIDE. If the mismatch is caused by analysis output,
write it in docs/requests/from-graph.md and tell me; do not edit analysis files.
Run make check, then /ship.
````

## STEP 7 — Artifacts, claims, reviews (Sat evening) 🚢
````
Branch: graph/claims.
Implement save_artifact, get_artifact, save_claim (upsert by claim_id), get_claim, list_claims (optional
status filter), save_review (INSERT only), list_reviews. Claims keep their revision number.
Tests: round trip of Artifact and Claim, reviews never lose rows, list by status.
Run make check, then /ship.
````

## STEP 8 — Staleness (Sat evening) 🚢
````
Branch: graph/staleness.
Implement mark_stale_for_changed_evidence(old_run_id, new_run_id): match evidence across runs by
(file, enclosing symbol / span); if a claim in the old run is ACCEPTED or EDITED and any cited
evidence's snippet_hash differs in the new run, set the claim STALE, keep the old decision in reviews,
return the list of claim_ids. Never auto-approve anything. Claims whose evidence is unchanged stay as
they are.
Tests: accept a claim -> modify one cited line (edit a temp copy of the sample or fixture via
aerotrace.analysis.demo_edit if present) -> claim becomes STALE; others stay ACCEPTED.
Run make check, then /ship. Tell me so I can tell Person 4.
````

## STEP 9 — Stretch (only when Steps 2-8 are merged and green)
````
Branch: graph/stretch. In this order, stopping when time runs out:
(a) export_subgraph(run_id, node_ids) -> {"nodes": [...], "edges": [...]} on the repo class so the UI can
    draw graphs; document the signature in docs/streams/graph.md.
(b) Optional Neo4j mirror in aerotrace/graph/neo4j_mirror.py: export the ACTIVE run; if Neo4j is
    unavailable everything else must still work.
(c) Record real timings (load, impact) in docs/streams/graph.md. Real numbers only.
Run make check, then /ship.
````

## STEP 10 — Final check (Sun 7 AM)
````
Run "status". Run make check on main. Make sure docs/streams/graph.md covers the schema summary, entry
points, traversal limits and staleness rule, and docs/progress/graph.md has a line per merged PR.
Docs-only fixes after the 8 AM freeze. /ship if there are doc changes.
````
