# AeroTrace

AeroTrace is our Honeywell Devils Invent (PS 1.1) project: a read-only, evidence-first tool that
turns a legacy C avionics repository into a source-linked graph, explains it with a tightly
limited LLM, and produces change-impact reports that humans review. Output is an engineering
aid, not certification evidence.

## Design rule

Static analysis builds the facts. The graph stores the facts. The LLM only explains facts it is
handed. Humans approve.

## Setup

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
make install            # creates .venv and installs requirements.txt (editable)
cp .env.example .env    # then fill in ANTHROPIC_API_KEY if you use the LLM; never commit .env
make check              # ruff check + pytest; must be green before every push
```

Other targets: `make fmt` (ruff format), `make demo`, `make ui` (both placeholders for now).

## Streams

Four streams, four owners. You only edit files inside your stream's paths.

| Stream | Who | Paths you may edit |
| --- | --- | --- |
| `analysis` | Person 1 | `aerotrace/ingest/`, `aerotrace/analysis/`, `demo/fixture/`, `demo/expected/`, `tests/analysis/`, `requirements/analysis.txt`, `docs/streams/analysis.md`, `docs/progress/analysis.md`, `docs/requests/from-analysis.md` |
| `graph` | Person 2 | `aerotrace/graph/`, `aerotrace/impact/`, `tests/graph/`, `requirements/graph.txt`, `docs/streams/graph.md`, `docs/progress/graph.md`, `docs/requests/from-graph.md` |
| `narrative` | Person 3 | `aerotrace/context/`, `aerotrace/narrative/`, `aerotrace/validators/`, `aerotrace/llm/`, `aerotrace/ask/`, `tests/narrative/`, `requirements/narrative.txt`, `docs/streams/narrative.md`, `docs/progress/narrative.md`, `docs/requests/from-narrative.md` |
| `app` | Person 4 | `aerotrace/service.py`, `aerotrace/api/`, `aerotrace/cli.py`, `aerotrace/review/`, `ui/`, `tests/e2e/`, `scripts/`, `Makefile`, `README.md`, `.github/`, `requirements/app.txt`, `docs/DEMO.md`, `docs/streams/app.md`, `docs/progress/app.md`, `docs/requests/from-app.md` |
| **LOCKED** | nobody (see §5) | `aerotrace/contracts/`, `docs/CONTRACTS.md`, `CLAUDE.md`, `.claude/`, `pyproject.toml`, `requirements.txt`, `requirements/base.txt`, `docs/DESIGN.md` |

## Contributing

**Read `CLAUDE.md` before contributing.** It defines folder ownership, the git workflow
(one branch per task, never push to `main`) and the merge cutoffs. Shared data shapes live in
`docs/CONTRACTS.md`; the full design is in `docs/DESIGN.md`.
