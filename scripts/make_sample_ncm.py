"""Build aerotrace/contracts/sample_ncm.json — a hand-written miniature of the demo fixture.

Scenario (CONTRACTS §7): a navigation-position message marked invalid or stale must not update
active navigation state. Seed for impact: NavMsg_IsValid.

Usage:
    python scripts/make_sample_ncm.py            # rewrite the JSON
    python scripts/make_sample_ncm.py --check    # exit 1 if the JSON is out of date
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run without installing

from aerotrace.contracts.ids import hash_bytes, make_id
from aerotrace.contracts.models import (
    AnalysisMethod,
    Edge,
    EdgeType,
    Evidence,
    FileCoverage,
    Node,
    NodeKind,
    NormalizedCodeModel,
    Quality,
    RunManifest,
)

OUTPUT = Path(__file__).resolve().parent.parent / "aerotrace" / "contracts" / "sample_ncm.json"

COMMIT = "5a3c1e0d9b7f4a2e8c6d1b0a9f8e7d6c5b4a3f21"
VARIANT = "baseline"
DEFINES = ["NAV_MAX_AGE_MS=200", "NAV_VARIANT_A"]
INCLUDE_PATHS = ["src/include"]
ANALYZER_VERSIONS = {"clang": "18.1.8", "tree_sitter_c": "0.23.0", "aerotrace_sample": "1"}
CREATED_AT = datetime(2026, 10, 2, 20, 0, 0, tzinfo=UTC)

NAV_TASK = "src/nav/nav_task.c"
NAV_MSG = "src/nav/nav_msg.c"
NAV_STATE = "src/nav/nav_state.c"
GUIDANCE = "src/guidance/guidance.c"
DISPLAY = "src/display/display.c"  # FALLBACK_PARSED (Tree-sitter only)
DISPATCH = "src/dispatch/dispatch.c"
NAV_GEN = "src/nav/nav_gen_tables.c"  # FAILED
TEST_NAV_MSG = "tests/test_nav_msg.c"

FALLBACK_FILES = {DISPLAY}


@dataclass(frozen=True)
class _Span:
    key: str
    file: str
    start_line: int
    end_line: int
    snippet: str


# Every source span that backs a node or an edge. Keys are only used inside this script.
_SPANS: list[_Span] = [
    # file headers (back File nodes and Module CONTAINS edges)
    _Span("file:" + NAV_TASK, NAV_TASK, 1, 1, "/* nav_task.c - periodic navigation task */"),
    _Span("file:" + NAV_MSG, NAV_MSG, 1, 1, "/* nav_msg.c - navigation message decode/check */"),
    _Span("file:" + NAV_STATE, NAV_STATE, 1, 1, "/* nav_state.c - active navigation state */"),
    _Span("file:" + GUIDANCE, GUIDANCE, 1, 1, "/* guidance.c - guidance law step */"),
    _Span("file:" + DISPLAY, DISPLAY, 1, 1, "/* display.c - cockpit display refresh */"),
    _Span("file:" + DISPATCH, DISPATCH, 1, 1, "/* dispatch.c - message dispatcher */"),
    _Span("file:" + TEST_NAV_MSG, TEST_NAV_MSG, 1, 1, "/* test_nav_msg.c - unit tests */"),
    # definitions
    _Span(
        "def:NavTask_Run",
        NAV_TASK,
        20,
        34,
        "void NavTask_Run(void)\n{\n    nav_msg_t msg;\n    NavMsg_Decode(&raw, &msg);\n"
        "    if (NavMsg_IsValid(&msg)) {\n        NavState_Update(&msg);\n    }\n"
        "    Guidance_Step();\n}",
    ),
    _Span(
        "def:NavMsg_Decode",
        NAV_MSG,
        22,
        40,
        "static void NavMsg_Decode(const uint8_t *raw, nav_msg_t *out)\n{\n"
        "    out->timestamp = rd_u32(raw);\n    out->position = rd_pos(raw + 4);\n}",
    ),
    _Span(
        "def:NavMsg_IsValid",
        NAV_MSG,
        45,
        60,
        "bool NavMsg_IsValid(const nav_msg_t *msg)\n{\n    if (!msg->valid) {\n        return false;\n"
        "    }\n    if (msg->timestamp <= g_nav_state.last_timestamp) {\n        return false;\n"
        "    }\n    return true;\n}",
    ),
    _Span(
        "def:NavState_Update",
        NAV_STATE,
        12,
        22,
        "void NavState_Update(const nav_msg_t *msg)\n{\n    g_nav_state.position = msg->position;\n"
        "    g_nav_state.last_timestamp = msg->timestamp;\n}",
    ),
    _Span("def:g_nav_state", NAV_STATE, 8, 8, "volatile nav_state_t g_nav_state;"),
    _Span(
        "def:Guidance_Step",
        GUIDANCE,
        35,
        50,
        "void Guidance_Step(void)\n{\n    pos_t p = g_nav_state.position;\n"
        "    steer_towards(p);\n    Display_Refresh();\n}",
    ),
    _Span(
        "def:Display_Refresh",
        DISPLAY,
        25,
        38,
        "void Display_Refresh(void)\n{\n    draw_position(g_nav_state.position);\n}",
    ),
    _Span(
        "def:Dispatch_Handle",
        DISPATCH,
        80,
        98,
        "void Dispatch_Handle(msg_ctx_t *ctx)\n{\n    g_handlers[ctx->id](ctx);\n"
        "    if (ctx->on_done) {\n        ctx->on_done(ctx);\n    }\n}",
    ),
    _Span(
        "def:test_NavMsg_IsValid_rejects_stale",
        TEST_NAV_MSG,
        25,
        33,
        "void test_NavMsg_IsValid_rejects_stale(void)\n{\n"
        "    TEST_ASSERT_FALSE(NavMsg_IsValid(&stale_msg));\n}",
    ),
    # edge sites
    _Span("site:run->decode", NAV_TASK, 24, 24, "NavMsg_Decode(&raw, &msg);"),
    _Span("site:run->isvalid", NAV_TASK, 25, 25, "if (NavMsg_IsValid(&msg)) {"),
    _Span("site:run->update", NAV_TASK, 26, 26, "NavState_Update(&msg);"),
    _Span("site:run->guidance", NAV_TASK, 29, 29, "Guidance_Step();"),
    _Span(
        "site:isvalid-reads",
        NAV_MSG,
        52,
        52,
        "if (msg->timestamp <= g_nav_state.last_timestamp) {",
    ),
    _Span(
        "site:update-writes",
        NAV_STATE,
        14,
        15,
        "g_nav_state.position = msg->position;\n    g_nav_state.last_timestamp = msg->timestamp;",
    ),
    _Span("site:guidance-reads", GUIDANCE, 37, 37, "pos_t p = g_nav_state.position;"),
    _Span("site:guidance->display", GUIDANCE, 39, 39, "Display_Refresh();"),
    _Span("site:display-reads", DISPLAY, 27, 27, "draw_position(g_nav_state.position);"),
    _Span("site:dispatch-maycall", DISPATCH, 82, 82, "g_handlers[ctx->id](ctx);"),
    _Span("site:dispatch-unresolved", DISPATCH, 85, 85, "ctx->on_done(ctx);"),
    _Span(
        "site:test-verifies", TEST_NAV_MSG, 27, 27, "TEST_ASSERT_FALSE(NavMsg_IsValid(&stale_msg));"
    ),
]


@dataclass(frozen=True)
class _NodeSpec:
    key: str
    kind: NodeKind
    name: str
    qualified_name: str
    file: str | None
    signature: str | None
    span_key: str | None
    properties: dict


_NODES: list[_NodeSpec] = [
    _NodeSpec("mod:nav", "Module", "nav", "nav", None, None, None, {"path": "src/nav"}),
    *[
        _NodeSpec("file:" + f, "File", f.rsplit("/", 1)[-1], f, f, None, "file:" + f, {})
        for f in (NAV_TASK, NAV_MSG, NAV_STATE, GUIDANCE, DISPLAY, DISPATCH, TEST_NAV_MSG)
    ],
    _NodeSpec(
        "fn:NavTask_Run",
        "Function",
        "NavTask_Run",
        "NavTask_Run",
        NAV_TASK,
        "void NavTask_Run(void)",
        "def:NavTask_Run",
        {},
    ),
    _NodeSpec(
        "fn:NavMsg_Decode",
        "Function",
        "NavMsg_Decode",
        f"{NAV_MSG}::NavMsg_Decode",
        NAV_MSG,
        "static void NavMsg_Decode(const uint8_t *raw, nav_msg_t *out)",
        "def:NavMsg_Decode",
        {"static": True},
    ),
    _NodeSpec(
        "fn:NavMsg_IsValid",
        "Function",
        "NavMsg_IsValid",
        "NavMsg_IsValid",
        NAV_MSG,
        "bool NavMsg_IsValid(const nav_msg_t *msg)",
        "def:NavMsg_IsValid",
        {},
    ),
    _NodeSpec(
        "fn:NavState_Update",
        "Function",
        "NavState_Update",
        "NavState_Update",
        NAV_STATE,
        "void NavState_Update(const nav_msg_t *msg)",
        "def:NavState_Update",
        {},
    ),
    _NodeSpec(
        "fn:Guidance_Step",
        "Function",
        "Guidance_Step",
        "Guidance_Step",
        GUIDANCE,
        "void Guidance_Step(void)",
        "def:Guidance_Step",
        {},
    ),
    _NodeSpec(
        "fn:Display_Refresh",
        "Function",
        "Display_Refresh",
        "Display_Refresh",
        DISPLAY,
        "void Display_Refresh(void)",
        "def:Display_Refresh",
        {},
    ),
    _NodeSpec(
        "fn:Dispatch_Handle",
        "Function",
        "Dispatch_Handle",
        "Dispatch_Handle",
        DISPATCH,
        "void Dispatch_Handle(msg_ctx_t *ctx)",
        "def:Dispatch_Handle",
        {},
    ),
    _NodeSpec(
        "var:g_nav_state",
        "Variable",
        "g_nav_state",
        "g_nav_state",
        NAV_STATE,
        "volatile nav_state_t g_nav_state",
        "def:g_nav_state",
        {"volatile": True},
    ),
    _NodeSpec(
        "test:rejects_stale",
        "Test",
        "test_NavMsg_IsValid_rejects_stale",
        "test_NavMsg_IsValid_rejects_stale",
        TEST_NAV_MSG,
        "void test_NavMsg_IsValid_rejects_stale(void)",
        "def:test_NavMsg_IsValid_rejects_stale",
        {"framework": "unity"},
    ),
    _NodeSpec(
        "ext:on_done",
        "ExternalSymbol",
        "ctx->on_done",
        f"{DISPATCH}:85:ctx->on_done",
        DISPATCH,
        None,
        "site:dispatch-unresolved",
        {"reason": "call through function pointer with no resolvable target"},
    ),
]

# (source key, target key, type, span key, properties)
_EDGES: list[tuple[str, str, EdgeType, str, dict]] = [
    *[
        ("mod:nav", "file:" + f, "CONTAINS", "file:" + f, {})
        for f in (NAV_TASK, NAV_MSG, NAV_STATE)
    ],
    ("file:" + NAV_TASK, "fn:NavTask_Run", "DEFINES", "def:NavTask_Run", {}),
    ("file:" + NAV_MSG, "fn:NavMsg_Decode", "DEFINES", "def:NavMsg_Decode", {}),
    ("file:" + NAV_MSG, "fn:NavMsg_IsValid", "DEFINES", "def:NavMsg_IsValid", {}),
    ("file:" + NAV_STATE, "fn:NavState_Update", "DEFINES", "def:NavState_Update", {}),
    ("file:" + NAV_STATE, "var:g_nav_state", "DEFINES", "def:g_nav_state", {}),
    ("file:" + GUIDANCE, "fn:Guidance_Step", "DEFINES", "def:Guidance_Step", {}),
    ("file:" + DISPLAY, "fn:Display_Refresh", "DEFINES", "def:Display_Refresh", {}),
    ("file:" + DISPATCH, "fn:Dispatch_Handle", "DEFINES", "def:Dispatch_Handle", {}),
    (
        "file:" + TEST_NAV_MSG,
        "test:rejects_stale",
        "DEFINES",
        "def:test_NavMsg_IsValid_rejects_stale",
        {},
    ),
    (
        "fn:NavTask_Run",
        "fn:NavMsg_Decode",
        "CALLS",
        "site:run->decode",
        {"call_site_line": 24, "order": 1},
    ),
    (
        "fn:NavTask_Run",
        "fn:NavMsg_IsValid",
        "CALLS",
        "site:run->isvalid",
        {"call_site_line": 25, "order": 2},
    ),
    (
        "fn:NavTask_Run",
        "fn:NavState_Update",
        "CALLS",
        "site:run->update",
        {"call_site_line": 26, "condition": "NavMsg_IsValid(&msg)", "order": 3},
    ),
    (
        "fn:NavTask_Run",
        "fn:Guidance_Step",
        "CALLS",
        "site:run->guidance",
        {"call_site_line": 29, "order": 4},
    ),
    (
        "fn:Guidance_Step",
        "fn:Display_Refresh",
        "CALLS",
        "site:guidance->display",
        {"call_site_line": 39, "order": 1},
    ),
    (
        "fn:NavMsg_IsValid",
        "var:g_nav_state",
        "READS",
        "site:isvalid-reads",
        {"field": "last_timestamp"},
    ),
    (
        "fn:NavState_Update",
        "var:g_nav_state",
        "WRITES",
        "site:update-writes",
        {"fields": ["position", "last_timestamp"]},
    ),
    ("fn:Guidance_Step", "var:g_nav_state", "READS", "site:guidance-reads", {"field": "position"}),
    ("fn:Display_Refresh", "var:g_nav_state", "READS", "site:display-reads", {"field": "position"}),
    (
        "fn:Dispatch_Handle",
        "fn:NavTask_Run",
        "MAY_CALL",
        "site:dispatch-maycall",
        {"call_site_line": 82, "via": "g_handlers[ctx->id]", "candidates": 1},
    ),
    (
        "fn:Dispatch_Handle",
        "ext:on_done",
        "UNRESOLVED_CALL",
        "site:dispatch-unresolved",
        {"call_site_line": 85},
    ),
    ("test:rejects_stale", "fn:NavMsg_IsValid", "VERIFIES", "site:test-verifies", {}),
]

_COVERAGE: list[FileCoverage] = [
    FileCoverage(file=NAV_TASK, status="PARSED"),
    FileCoverage(file=NAV_MSG, status="PARSED"),
    FileCoverage(file=NAV_STATE, status="PARSED"),
    FileCoverage(file=GUIDANCE, status="PARSED"),
    FileCoverage(
        file=DISPLAY,
        status="FALLBACK_PARSED",
        reason="clang failed: unknown type 'gfx_ctx_t'; parsed with Tree-sitter",
    ),
    FileCoverage(file=DISPATCH, status="PARSED"),
    FileCoverage(file=NAV_GEN, status="FAILED", reason="missing header nav_gen.h"),
    FileCoverage(file=TEST_NAV_MSG, status="PARSED"),
]

_KNOWN_GAPS: list[str] = [
    f"unresolved callback at {DISPATCH}:85 (ctx->on_done)",
    f"{DISPATCH}:82 calls through g_handlers table; target set is a possible, not proven, call",
    f"{NAV_GEN} failed to parse: missing header nav_gen.h",
    f"{DISPLAY} parsed with Tree-sitter fallback; its reads/writes are not PRECISE",
]


def make_run_id(
    commit: str,
    variant: str,
    defines: list[str],
    include_paths: list[str],
    analyzer_versions: dict[str, str],
) -> str:
    """Return the run_id per CONTRACTS §3 (commit, variant, sorted defines/includes, versions)."""
    return make_id(
        commit,
        variant,
        ",".join(sorted(defines)),
        ",".join(sorted(include_paths)),
        ",".join(f"{k}={v}" for k, v in sorted(analyzer_versions.items())),
    )


def _evidence(span: _Span, snippet: str) -> Evidence:
    data = snippet.encode("utf-8")
    start_byte = (span.start_line - 1) * 40
    end_byte = start_byte + len(data)
    snippet_hash = hash_bytes(data)
    fallback = span.file in FALLBACK_FILES
    method: AnalysisMethod = "tree_sitter" if fallback else "clang"
    quality: Quality = "FALLBACK_PARSED" if fallback else "PRECISE"
    return Evidence(
        evidence_id=make_id(span.file, str(start_byte), str(end_byte), snippet_hash),
        file=span.file,
        start_line=span.start_line,
        end_line=span.end_line,
        start_byte=start_byte,
        end_byte=end_byte,
        snippet_hash=snippet_hash,
        snippet=snippet,
        analysis_method=method,
        quality=quality,
    )


def build_sample_ncm(
    commit: str = COMMIT, snippet_overrides: dict[str, str] | None = None
) -> NormalizedCodeModel:
    """Build the sample NCM deterministically.

    Inputs: ``commit`` (changes run_id) and ``snippet_overrides`` mapping a span key such as
    ``"def:NavMsg_IsValid"`` to new source text — used to simulate an edited file for staleness
    tests. Output: a validated NormalizedCodeModel. Raises KeyError for an unknown span key.
    """
    overrides = snippet_overrides or {}
    known = {s.key for s in _SPANS}
    for key in overrides:
        if key not in known:
            raise KeyError(f"unknown span key: {key}")

    evidence_by_key = {s.key: _evidence(s, overrides.get(s.key, s.snippet)) for s in _SPANS}
    span_by_key = {s.key: s for s in _SPANS}

    node_ids: dict[str, str] = {}
    nodes: list[Node] = []
    for spec in _NODES:
        node_id = make_id(spec.kind, spec.file or "", spec.qualified_name, spec.signature or "")
        node_ids[spec.key] = node_id
        span = span_by_key.get(spec.span_key) if spec.span_key else None
        is_file = spec.kind == "File"
        nodes.append(
            Node(
                id=node_id,
                kind=spec.kind,
                name=spec.name,
                qualified_name=spec.qualified_name,
                file=spec.file,
                start_line=None if span is None or is_file else span.start_line,
                end_line=None if span is None or is_file else span.end_line,
                signature=spec.signature,
                evidence_ids=[evidence_by_key[spec.span_key].evidence_id] if spec.span_key else [],
                properties=dict(spec.properties),
            )
        )

    edges = [
        Edge(
            source=node_ids[src],
            target=node_ids[dst],
            type=etype,
            evidence_ids=[evidence_by_key[span_key].evidence_id],
            properties=dict(props),
        )
        for src, dst, etype, span_key, props in _EDGES
    ]

    manifest = RunManifest(
        run_id=make_run_id(commit, VARIANT, DEFINES, INCLUDE_PATHS, ANALYZER_VERSIONS),
        repo_path="demo/fixture",
        commit=commit,
        dirty=False,
        variant=VARIANT,
        defines=list(DEFINES),
        include_paths=list(INCLUDE_PATHS),
        build_context="PARTIAL",
        analyzer_versions=dict(ANALYZER_VERSIONS),
        created_at=CREATED_AT,
    )
    return NormalizedCodeModel(
        manifest=manifest,
        nodes=nodes,
        edges=edges,
        evidence=sorted(evidence_by_key.values(), key=lambda e: (e.file, e.start_byte)),
        coverage=[c.model_copy() for c in _COVERAGE],
        known_gaps=list(_KNOWN_GAPS),
    )


def render_sample_json() -> str:
    """Return the sample NCM as the exact JSON text stored in sample_ncm.json."""
    return build_sample_ncm().model_dump_json(indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the JSON is out of date")
    args = parser.parse_args(argv)
    text = render_sample_json()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print(
                f"{OUTPUT} is out of date; run python scripts/make_sample_ncm.py", file=sys.stderr
            )
            return 1
        print(f"{OUTPUT} is up to date")
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
