# App stream

Owns the service layer (`aerotrace/service.py`) that the UI, CLI and API call. Nothing else
calls the other streams directly. It uses only the entry points in `docs/CONTRACTS.md`
(`run_analysis`, `open_repository`, `compute_impact`, `generate_artifact`, `answer`) and the
types in `aerotrace.contracts`. Today those entry points are stubs that call the fakes.

## `aerotrace.service` (public)

| Function | Returns | Notes |
| --- | --- | --- |
| `analyze(repo_path, variant="baseline")` | `RunManifest` | analysis -> `load_model` -> `activate`; `FileNotFoundError` if the folder is missing; the previous run stays active on failure |
| `reanalyze(repo_path, variant="baseline")` | `{new_run_id, old_run_id, stale_claim_ids}` | analyze again, then `mark_stale_for_changed_evidence(old, new)` |
| `overview(run_id)` | dict | manifest, `build_context`, `coverage_counts` (PARSED / FALLBACK_PARSED / FAILED / SKIPPED), `unresolved_call_count`, `known_gaps` |
| `search(run_id, q, kinds=None, limit=20)` | `list[Node]` | blank `q` lists nothing unless `kinds` is given |
| `artifact(run_id, kind, subject_id, use_llm=True)` | `Artifact` | stored with its claims so they can be reviewed |
| `impact(run_id, seed_ids)` | `ImpactResult` | `ValueError` if no seeds |
| `ask(run_id, question)` | `AskAnswer` | claims are stored; `ValueError` if blank |
| `evidence(run_id, evidence_id)` | `{evidence, source_lines, status, hash_ok, message}` | see below |
| `repository()`, `db_path()`, `llm_enabled()`, `reset()` | | shared repository handle, config, test reset |

### Evidence is verified, never trusted

`evidence()` reads the file from `manifest.repo_path`, re-hashes the exact byte span and compares
it with the stored `snippet_hash`. Only a matching span is returned as `source_lines` (the span
plus two lines of context; each line is `{line, text, in_span}`). Otherwise `source_lines` is
`None` and `status` is one of `HASH_MISMATCH`, `FILE_MISSING`, `SPAN_OUT_OF_RANGE`,
`PATH_OUTSIDE_REPO`, `UNREADABLE`. A shifted span is flagged, not searched for.

### Behaviour worth knowing

- Config: `AEROTRACE_DB` (default `.aerotrace/aerotrace.db`) and `AEROTRACE_LLM_PROVIDER`; a
  `.env` is loaded without overriding real environment variables.
- The LLM is used only when the provider is `anthropic` **and** `use_llm` is true. Anything else
  gives template-only output.
- Regenerating an artifact or re-asking a question keeps claims a reviewer already acted on.
- The repository handle is cached per database path, because the stub `open_repository`
  returns a fresh in-memory repository on every call.

## Run the backend

Run the backend: `make api` or `python -m aerotrace.api.main` (entry: `aerotrace/api/main.py`, health check at `/health`). Routes that expose `aerotrace.service` are still to be added.

## Run the tests

`make check` (ruff + pytest). Service tests: `tests/e2e/test_service.py`.

## Current limits

- Runs on the fakes until the real analysis, graph, impact and narrative streams merge.
- `unresolved_call_count` lists ExternalSymbol nodes with a blank query plus `kinds`; this is
  the `[contracts] find_symbols` change. The real graph repository must support it.
- `reanalyze` compares runs by `run_id`. If analysis gives the same `run_id` to an edited,
  uncommitted working tree, no claim can be marked stale. Analysis should fold the dirty state
  into `run_id` (see `docs/requests/from-app.md`).
