# AeroTrace Contracts (LOCKED)

These shapes live in `aerotrace/contracts/` as Pydantic v2 models. Every stream builds against
them. Change only through the process in `CLAUDE.md` §5 (additive changes only).

## 1. How the streams connect

```
Person 1 (analysis)                Person 2 (graph)                    Person 3 (narrative)            Person 4 (app)
run_analysis(repo) ──NCM──▶  repo.load_model(ncm) ─▶ activate()
                                   GraphRepository  ◀──── reads ────  generate_artifact(...)  ◀──── service.py ◀── UI / CLI / API
                                   compute_impact(...) ◀───────────── (impact dossier)
                                   save_claim / save_review  ◀──────────────────────────────── review/ (accept, edit, reject)
                                   mark_stale_for_changed_evidence ◀────────────────────────── service.reanalyze()
```

## 2. Entry points (the ONLY cross-stream calls allowed)

| Stream | Entry point |
| --- | --- |
| analysis | `aerotrace.analysis.run_analysis(repo_path: Path, variant: str = "baseline", compile_db: Path \| None = None) -> NormalizedCodeModel` |
| graph | `aerotrace.graph.open_repository(db_path: Path) -> GraphRepository` |
| graph | `aerotrace.impact.compute_impact(repo: GraphRepository, run_id: str, seed_ids: list[str], limits: TraversalLimits \| None = None) -> ImpactResult` |
| narrative | `aerotrace.narrative.generate_artifact(repo: GraphRepository, run_id: str, kind: ArtifactKind, subject_id: str, use_llm: bool = True) -> Artifact` |
| narrative | `aerotrace.ask.answer(repo: GraphRepository, run_id: str, question: str) -> AskAnswer` |
| app | `aerotrace.service` functions (used by UI, CLI, API — not by other streams) |

Until the real one is merged, use the matching fake from `aerotrace/contracts/fakes.py`:
`fake_run_analysis`, `FakeGraphRepository`, `fake_compute_impact`, `fake_generate_artifact`, `fake_answer`.

## 3. IDs

`aerotrace.contracts.ids.make_id(*parts: str) -> str` returns `"sha256:" + hex(sha256("\x1f".join(parts)))`.

| ID | Built from |
| --- | --- |
| `run_id` | commit, variant, sorted defines, sorted include paths, analyzer versions |
| `symbol_id` (node) | kind, file path, qualified name, signature (so two `static` functions in different files differ) |
| `evidence_id` | file path, start_byte, end_byte, snippet_hash |
| `claim_id` | artifact_id, subject_id, claim index |

Same inputs → same IDs. Both analysis and graph streams must use `make_id`, never their own hashing.

## 4. Enums

```python
NodeKind = Literal["Module", "File", "Function", "Variable", "ExternalSymbol", "Test"]
EdgeType = Literal[
    "CONTAINS",
    "DEFINES",
    "INCLUDES",
    "CALLS",
    "MAY_CALL",
    "UNRESOLVED_CALL",
    "READS",
    "WRITES",
    "GUARDED_BY",
    "VERIFIES",
]
Origin = Literal["DETERMINISTIC_ANALYZER", "CONFIG_PARSER", "TEMPLATE", "LLM_NARRATIVE", "HUMAN"]
AnalysisMethod = Literal["clang", "tree_sitter", "config", "regex"]
Quality = Literal["PRECISE", "FALLBACK_PARSED"]
BuildContext = Literal["COMPLETE", "PARTIAL", "UNKNOWN"]
FileStatus = Literal["PARSED", "FALLBACK_PARSED", "FAILED", "SKIPPED"]
Classification = Literal["SUPPORTED", "INFERRED", "ASSUMED", "UNKNOWN", "CONFLICTING"]
ClaimStatus = Literal[
    "UNREVIEWED", "ACCEPTED", "EDITED", "REJECTED", "NEEDS_INVESTIGATION", "STALE"
]
ReviewAction = Literal["ACCEPT", "EDIT", "REJECT", "INVESTIGATE"]
ArtifactKind = Literal[
    "function_card", "call_tree", "data_flow", "sequence", "module_card", "impact_dossier"
]
```

## 5. Models (`aerotrace/contracts/models.py`)

```python
class Evidence(BaseModel):
    evidence_id: str
    file: str  # repo-relative, forward slashes
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    snippet_hash: str  # sha256 of the exact source bytes in the span
    snippet: str | None = None  # optional short copy for display
    analysis_method: AnalysisMethod
    quality: Quality


class Node(BaseModel):
    id: str
    kind: NodeKind
    name: str
    qualified_name: str
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    signature: str | None = None
    origin: Origin = "DETERMINISTIC_ANALYZER"
    evidence_ids: list[str] = []
    properties: dict[
        str, Any
    ] = {}  # e.g. {"static": true, "volatile": true, "ifdef": "NAV_VARIANT_B"}


class Edge(BaseModel):
    source: str
    target: str  # for UNRESOLVED_CALL: an ExternalSymbol node describing the unknown target
    type: EdgeType
    origin: Origin = "DETERMINISTIC_ANALYZER"
    evidence_ids: list[str]  # must be non-empty
    properties: dict[
        str, Any
    ] = {}  # CALLS: {"call_site_line": 145, "condition": "msg->valid", "order": 3}


class FileCoverage(BaseModel):
    file: str
    status: FileStatus
    reason: str | None = None  # e.g. "missing header nav_gen.h", "binary", "vendor"


class RunManifest(BaseModel):
    run_id: str
    repo_path: str
    commit: str | None
    dirty: bool
    variant: str
    defines: list[str]
    include_paths: list[str]
    build_context: BuildContext
    analyzer_versions: dict[str, str]
    created_at: datetime


class NormalizedCodeModel(BaseModel):
    manifest: RunManifest
    nodes: list[Node]
    edges: list[Edge]
    evidence: list[Evidence]
    coverage: list[FileCoverage]
    known_gaps: list[str]  # human-readable, e.g. "unresolved callback at dispatch.c:88"


class TraversalLimits(BaseModel):
    max_depth: int = 6
    max_nodes: int = 500
    max_edges: int = 1500
    timeout_s: float = 5.0


class PathHop(BaseModel):
    source: str
    target: str
    edge_type: EdgeType
    evidence_ids: list[str]


class ImpactItem(BaseModel):
    node_id: str
    name: str
    path: list[PathHop]  # full path from seed to this node
    reason: str  # short deterministic reason


class ImpactResult(BaseModel):
    run_id: str
    seed_ids: list[str]
    direct: list[ImpactItem]
    transitive: list[ImpactItem]
    verification: list[ImpactItem]
    uncertain_frontier: list[ImpactItem]
    truncated: bool = False
    truncation_reason: str | None = None
    empty_message: str | None = None  # fixed wording from DESIGN §4.10 when nothing found


class ContextBundle(BaseModel):
    task: ArtifactKind
    run_scope: dict[str, Any]  # {"run_id", "commit", "variant", "build_context"}
    subject: dict[str, Any]  # {"symbol_id", "name", "signature"}
    facts: list[dict[str, Any]]  # structured facts from the graph
    evidence: list[Evidence]
    allowed_evidence_ids: list[str]
    known_gaps: list[str]


class Claim(BaseModel):
    claim_id: str
    run_id: str
    artifact_id: str
    subject_id: str
    text: str
    classification: Classification
    evidence_ids: list[str]
    origin: Origin  # TEMPLATE | LLM_NARRATIVE | HUMAN
    status: ClaimStatus = "UNREVIEWED"
    revision: int = 0
    assumptions: list[str] = []
    open_questions: list[str] = []


class ValidationReport(BaseModel):
    passed: bool
    errors: list[str] = []
    fell_back_to_template: bool = False


class Artifact(BaseModel):
    artifact_id: str
    run_id: str
    kind: ArtifactKind
    subject_id: str
    structured: dict[str, Any]  # deterministic skeleton (callers, callees, tree, paths, ...)
    mermaid: str | None = None  # call tree / sequence diagrams; sanitized
    claims: list[Claim]
    generated_by: Literal["TEMPLATE", "LLM"]
    validation: ValidationReport
    banner: str = "Engineering aid — not certification evidence. Advisory; requires independent engineering review."


class ReviewEvent(BaseModel):
    event_id: str
    claim_id: str
    action: ReviewAction
    reviewer: str
    rationale: str | None = None
    new_text: str | None = None  # only for EDIT
    run_id: str
    timestamp: datetime


class AskAnswer(BaseModel):
    question: str
    tool_calls: list[dict[str, Any]]  # which typed tools were used, with args
    artifact: Artifact | None
    text: str
    claims: list[Claim]
```

## 6. GraphRepository protocol (`aerotrace/contracts/repository.py`)

```python
class GraphRepository(Protocol):
    # build
    def load_model(self, ncm: NormalizedCodeModel) -> str: ...  # stages it, returns run_id
    def activate(self, run_id: str) -> None: ...  # validate then make active
    def active_run_id(self) -> str | None: ...
    def get_manifest(self, run_id: str) -> RunManifest: ...
    def get_coverage(self, run_id: str) -> list[FileCoverage]: ...
    def get_known_gaps(self, run_id: str) -> list[str]: ...
    # read
    def get_node(self, run_id: str, node_id: str) -> Node | None: ...
    def find_symbols(
        self, run_id: str, query: str, kinds: list[NodeKind] | None = None, limit: int = 20
    ) -> list[Node]: ...
    def edges_from(
        self, run_id: str, node_id: str, types: list[EdgeType] | None = None
    ) -> list[Edge]: ...
    def edges_to(
        self, run_id: str, node_id: str, types: list[EdgeType] | None = None
    ) -> list[Edge]: ...
    def get_evidence(self, run_id: str, evidence_id: str) -> Evidence | None: ...
    def bounded_traversal(
        self,
        run_id: str,
        seed_id: str,
        types: list[EdgeType],
        direction: Literal["out", "in"],
        limits: TraversalLimits | None = None,
    ) -> tuple[list[list[PathHop]], bool, str | None]: ...
    #   returns (paths, truncated, truncation_reason)
    # claims and review
    def save_artifact(self, artifact: Artifact) -> None: ...
    def get_artifact(self, artifact_id: str) -> Artifact | None: ...
    def save_claim(self, claim: Claim) -> None: ...
    def get_claim(self, claim_id: str) -> Claim | None: ...
    def list_claims(self, run_id: str, status: ClaimStatus | None = None) -> list[Claim]: ...
    def save_review(self, event: ReviewEvent) -> None: ...  # append-only
    def list_reviews(self, claim_id: str) -> list[ReviewEvent]: ...
    # staleness
    def mark_stale_for_changed_evidence(self, old_run_id: str, new_run_id: str) -> list[str]: ...

    #   claims that were ACCEPTED/EDITED and whose cited evidence hash changed → STALE; returns claim_ids
```

## 7. Demo scenario everyone targets

*"A navigation-position message marked invalid or stale must not update active navigation state.
What is affected if we change the stale-data handling?"*

Seed function for impact: `NavMsg_IsValid` (in `demo/fixture/src/nav/nav_msg.c`).
`aerotrace/contracts/sample_ncm.json` is a hand-written miniature of this fixture so every stream can
work before the real parser exists.
