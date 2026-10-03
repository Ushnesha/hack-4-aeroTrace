"""Contract tests: sample NCM, IDs, FakeGraphRepository, fakes and stub entry points."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aerotrace.analysis import run_analysis
from aerotrace.ask import answer
from aerotrace.contracts import (
    FakeGraphRepository,
    GraphRepository,
    NormalizedCodeModel,
    ReviewEvent,
    TraversalLimits,
    fake_answer,
    fake_compute_impact,
    fake_generate_artifact,
    fake_run_analysis,
    hash_bytes,
    load_sample_ncm,
    make_id,
)
from aerotrace.contracts.fakes import EMPTY_IMPACT_MESSAGE, SAMPLE_NCM_PATH
from aerotrace.graph import open_repository
from aerotrace.impact import compute_impact
from aerotrace.narrative import generate_artifact

ROOT = Path(__file__).resolve().parent.parent


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "make_sample_ncm", ROOT / "scripts" / "make_sample_ncm.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_sample_ncm"] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


@pytest.fixture()
def ncm() -> NormalizedCodeModel:
    return load_sample_ncm()


@pytest.fixture()
def repo(ncm: NormalizedCodeModel) -> FakeGraphRepository:
    r = FakeGraphRepository()
    run_id = r.load_model(ncm)
    r.activate(run_id)
    return r


def _id(ncm: NormalizedCodeModel, name: str) -> str:
    return next(n.id for n in ncm.nodes if n.name == name)


# --- ids --------------------------------------------------------------------------------------


def test_make_id_format_and_separator() -> None:
    assert make_id("a", "b") == make_id("a", "b")
    assert make_id("a", "b").startswith("sha256:")
    assert len(make_id("a")) == len("sha256:") + 64
    assert make_id("ab", "c") != make_id("a", "bc")
    assert make_id("a", "b") != make_id("b", "a")


def test_make_id_rejects_non_str() -> None:
    with pytest.raises(TypeError):
        make_id("a", 1)  # type: ignore[arg-type]


def test_hash_bytes_style() -> None:
    assert hash_bytes(b"x") == hash_bytes(b"x")
    assert hash_bytes(b"x") != hash_bytes(b"y")
    assert hash_bytes(b"").startswith("sha256:")


# --- sample -----------------------------------------------------------------------------------


def test_sample_loads_and_validates(ncm: NormalizedCodeModel) -> None:
    assert ncm.manifest.build_context == "PARTIAL"
    names = {n.name for n in ncm.nodes if n.kind == "Function"}
    assert {
        "NavTask_Run",
        "NavMsg_Decode",
        "NavMsg_IsValid",
        "NavState_Update",
        "Guidance_Step",
        "Display_Refresh",
        "Dispatch_Handle",
    } <= names
    assert any(n.name == "g_nav_state" and n.kind == "Variable" for n in ncm.nodes)
    assert any(n.kind == "Test" for n in ncm.nodes)
    assert any(n.kind == "ExternalSymbol" for n in ncm.nodes)
    types = {e.type for e in ncm.edges}
    assert {"READS", "WRITES", "MAY_CALL", "UNRESOLVED_CALL", "VERIFIES", "CALLS"} <= types
    statuses = {c.status for c in ncm.coverage}
    assert {"FALLBACK_PARSED", "FAILED", "PARSED"} <= statuses


def test_every_edge_evidence_exists(ncm: NormalizedCodeModel) -> None:
    evidence_ids = {e.evidence_id for e in ncm.evidence}
    node_ids = {n.id for n in ncm.nodes}
    assert len(evidence_ids) == len(ncm.evidence)
    for edge in ncm.edges:
        assert edge.evidence_ids, f"edge {edge.type} has no evidence"
        assert set(edge.evidence_ids) <= evidence_ids
        assert edge.source in node_ids and edge.target in node_ids
    for node in ncm.nodes:
        assert set(node.evidence_ids) <= evidence_ids


def test_evidence_hash_matches_snippet(ncm: NormalizedCodeModel) -> None:
    for ev in ncm.evidence:
        assert ev.snippet is not None
        assert ev.snippet_hash == hash_bytes(ev.snippet.encode("utf-8"))
        assert ev.evidence_id == make_id(
            ev.file, str(ev.start_byte), str(ev.end_byte), ev.snippet_hash
        )


def test_fallback_file_has_fallback_evidence(ncm: NormalizedCodeModel) -> None:
    display = [e for e in ncm.evidence if e.file.endswith("display.c")]
    assert display and all(e.quality == "FALLBACK_PARSED" for e in display)
    assert all(e.analysis_method == "tree_sitter" for e in display)


def test_ids_stable_across_two_builds() -> None:
    a = script.build_sample_ncm()
    b = script.build_sample_ncm()
    assert a.model_dump_json() == b.model_dump_json()
    assert a.manifest.run_id == b.manifest.run_id
    assert [n.id for n in a.nodes] == [n.id for n in b.nodes]


def test_checked_in_json_is_up_to_date() -> None:
    assert SAMPLE_NCM_PATH.read_text(encoding="utf-8") == script.render_sample_json()


def test_static_functions_in_different_files_get_different_ids() -> None:
    a = make_id("Function", "a.c", "a.c::helper", "static void helper(void)")
    b = make_id("Function", "b.c", "b.c::helper", "static void helper(void)")
    assert a != b


def test_run_id_changes_with_commit() -> None:
    assert (
        script.build_sample_ncm("a" * 40).manifest.run_id
        != script.build_sample_ncm("b" * 40).manifest.run_id
    )


def test_unknown_snippet_override_raises() -> None:
    with pytest.raises(KeyError):
        script.build_sample_ncm(snippet_overrides={"nope": "x"})


# --- repository: build and read ---------------------------------------------------------------


def test_fake_repository_satisfies_protocol() -> None:
    repo: GraphRepository = FakeGraphRepository()
    assert repo.active_run_id() is None


def test_load_activate_and_manifest(ncm: NormalizedCodeModel) -> None:
    r = FakeGraphRepository()
    run_id = r.load_model(ncm)
    assert r.active_run_id() is None  # staged only
    r.activate(run_id)
    assert r.active_run_id() == run_id
    assert r.get_manifest(run_id) == ncm.manifest
    assert r.get_coverage(run_id) == ncm.coverage
    assert r.get_known_gaps(run_id) == ncm.known_gaps


def test_activate_rejects_dangling_evidence(ncm: NormalizedCodeModel) -> None:
    broken = ncm.model_copy(
        update={"edges": [ncm.edges[0].model_copy(update={"evidence_ids": ["sha256:missing"]})]}
    )
    r = FakeGraphRepository()
    run_id = r.load_model(broken)
    with pytest.raises(ValueError, match="missing evidence"):
        r.activate(run_id)
    assert r.active_run_id() is None


def test_unknown_run_raises(repo: FakeGraphRepository) -> None:
    with pytest.raises(KeyError):
        repo.get_manifest("sha256:nope")


def test_find_symbols_and_get_node(repo: FakeGraphRepository, ncm: NormalizedCodeModel) -> None:
    run_id = ncm.manifest.run_id
    hits = repo.find_symbols(run_id, "navmsg_isvalid")
    assert [h.name for h in hits] == ["NavMsg_IsValid", "test_NavMsg_IsValid_rejects_stale"]
    assert repo.get_node(run_id, hits[0].id) == hits[0]
    assert repo.get_node(run_id, "sha256:nope") is None
    assert [n.name for n in repo.find_symbols(run_id, "nav", kinds=["Variable"])] == ["g_nav_state"]
    assert len(repo.find_symbols(run_id, "nav", limit=2)) == 2
    assert repo.find_symbols(run_id, "  ") == []
    assert repo.find_symbols(run_id, "", limit=5) == []  # blank without kinds: nothing
    externals = repo.find_symbols(run_id, "", kinds=["ExternalSymbol"])
    assert [n.name for n in externals] == ["ctx->on_done"]
    functions = repo.find_symbols(run_id, "  ", kinds=["Function"], limit=100)
    assert len(functions) == 7 and functions == sorted(functions, key=lambda n: (n.name, n.id))


def test_edges_and_evidence(repo: FakeGraphRepository, ncm: NormalizedCodeModel) -> None:
    run_id = ncm.manifest.run_id
    run = _id(ncm, "NavTask_Run")
    out = repo.edges_from(run_id, run, ["CALLS"])
    assert len(out) == 4
    assert all(e.source == run for e in out)
    assert [e.properties["order"] for e in out] != []
    into = repo.edges_to(run_id, _id(ncm, "NavMsg_IsValid"), ["CALLS"])
    assert [e.source for e in into] == [run]
    ev = repo.get_evidence(run_id, out[0].evidence_ids[0])
    assert ev is not None and ev.file.endswith("nav_task.c")
    assert repo.get_evidence(run_id, "sha256:nope") is None


# --- repository: traversal --------------------------------------------------------------------


def test_bounded_traversal_out(repo: FakeGraphRepository, ncm: NormalizedCodeModel) -> None:
    run_id = ncm.manifest.run_id
    paths, truncated, reason = repo.bounded_traversal(
        run_id, _id(ncm, "NavTask_Run"), ["CALLS"], "out"
    )
    assert not truncated and reason is None
    reached = {p[-1].target for p in paths}
    assert reached == {
        _id(ncm, n)
        for n in (
            "NavMsg_Decode",
            "NavMsg_IsValid",
            "NavState_Update",
            "Guidance_Step",
            "Display_Refresh",
        )
    }
    display = next(p for p in paths if p[-1].target == _id(ncm, "Display_Refresh"))
    assert [h.source for h in display] == [_id(ncm, "NavTask_Run"), _id(ncm, "Guidance_Step")]
    assert all(h.evidence_ids for p in paths for h in p)
    assert [len(p) for p in paths] == sorted(len(p) for p in paths)


def test_bounded_traversal_in_keeps_real_edge_direction(
    repo: FakeGraphRepository, ncm: NormalizedCodeModel
) -> None:
    run_id = ncm.manifest.run_id
    paths, _, _ = repo.bounded_traversal(
        run_id, _id(ncm, "NavMsg_IsValid"), ["CALLS", "MAY_CALL"], "in"
    )
    names = {p[-1].source: p for p in paths}
    assert set(names) == {_id(ncm, "NavTask_Run"), _id(ncm, "Dispatch_Handle")}
    hop = names[_id(ncm, "NavTask_Run")][0]
    assert hop.source == _id(ncm, "NavTask_Run") and hop.target == _id(ncm, "NavMsg_IsValid")


def test_bounded_traversal_limits(repo: FakeGraphRepository, ncm: NormalizedCodeModel) -> None:
    run_id = ncm.manifest.run_id
    seed = _id(ncm, "NavTask_Run")
    _, truncated, reason = repo.bounded_traversal(
        run_id, seed, ["CALLS"], "out", TraversalLimits(max_depth=1)
    )
    assert truncated and "max_depth" in (reason or "")
    paths, truncated, reason = repo.bounded_traversal(
        run_id, seed, ["CALLS"], "out", TraversalLimits(max_nodes=2)
    )
    assert truncated and "max_nodes" in (reason or "") and len(paths) == 2
    _, truncated, reason = repo.bounded_traversal(
        run_id, seed, ["CALLS"], "out", TraversalLimits(max_edges=1)
    )
    assert truncated and "max_edges" in (reason or "")
    assert repo.bounded_traversal(run_id, "sha256:nope", ["CALLS"], "out") == ([], False, None)


def test_traversal_terminates_on_cycles(ncm: NormalizedCodeModel) -> None:
    # Dispatch_Handle -MAY_CALL-> NavTask_Run; add a back edge to make a cycle.
    run, dispatch = _id(ncm, "NavTask_Run"), _id(ncm, "Dispatch_Handle")
    back = ncm.edges[-1].model_copy(update={"source": run, "target": dispatch, "type": "MAY_CALL"})
    cyclic = ncm.model_copy(update={"edges": [*ncm.edges, back]})
    r = FakeGraphRepository()
    run_id = r.load_model(cyclic)
    paths, truncated, _ = r.bounded_traversal(run_id, run, ["CALLS", "MAY_CALL"], "out")
    assert not truncated
    assert len({p[-1].target for p in paths}) == len(paths)


# --- repository: claims, review, staleness ----------------------------------------------------


def _review(claim_id: str, run_id: str, action: str = "ACCEPT") -> ReviewEvent:
    return ReviewEvent(
        event_id=make_id("review", claim_id, action),
        claim_id=claim_id,
        action=action,  # type: ignore[arg-type]
        reviewer="tester",
        run_id=run_id,
        timestamp=datetime(2026, 10, 3, 9, 0, tzinfo=UTC),
    )


def test_artifact_claim_and_review_roundtrip(
    repo: FakeGraphRepository, ncm: NormalizedCodeModel
) -> None:
    run_id = ncm.manifest.run_id
    artifact = fake_generate_artifact(repo, run_id, "function_card", _id(ncm, "NavMsg_IsValid"))
    repo.save_artifact(artifact)
    assert repo.get_artifact(artifact.artifact_id) == artifact
    claim = artifact.claims[0]
    assert repo.get_claim(claim.claim_id) == claim
    assert repo.list_claims(run_id) == sorted(artifact.claims, key=lambda c: c.claim_id)
    assert repo.list_claims(run_id, "ACCEPTED") == []
    repo.save_review(_review(claim.claim_id, run_id, "ACCEPT"))
    repo.save_review(_review(claim.claim_id, run_id, "INVESTIGATE"))
    assert [e.action for e in repo.list_reviews(claim.claim_id)] == ["ACCEPT", "INVESTIGATE"]
    assert repo.list_reviews("sha256:nope") == []
    assert repo.get_artifact("sha256:nope") is None and repo.get_claim("sha256:nope") is None


def test_staleness_marks_only_changed_accepted_claims(ncm: NormalizedCodeModel) -> None:
    repo = FakeGraphRepository()
    old_id = repo.load_model(ncm)
    repo.activate(old_id)

    isvalid = _id(ncm, "NavMsg_IsValid")
    update = _id(ncm, "NavState_Update")
    changed = fake_generate_artifact(repo, old_id, "function_card", isvalid).claims[0]
    unchanged = fake_generate_artifact(repo, old_id, "function_card", update).claims[0]
    unreviewed = fake_generate_artifact(repo, old_id, "function_card", isvalid).claims[0]
    assert changed.claim_id == unreviewed.claim_id  # same artifact -> same claim_id

    other = fake_generate_artifact(repo, old_id, "call_tree", isvalid).claims[0]
    for c in (changed, unchanged):
        repo.save_claim(c.model_copy(update={"status": "ACCEPTED"}))
    repo.save_claim(other.model_copy(update={"status": "UNREVIEWED"}))

    new_ncm = script.build_sample_ncm(
        commit="c" * 40,
        snippet_overrides={"def:NavMsg_IsValid": "bool NavMsg_IsValid(...) { /* edited */ }"},
    )
    new_id = repo.load_model(new_ncm)
    assert new_id != old_id

    stale = repo.mark_stale_for_changed_evidence(old_id, new_id)
    assert stale == [changed.claim_id]
    assert repo.get_claim(changed.claim_id).status == "STALE"
    assert repo.get_claim(unchanged.claim_id).status == "ACCEPTED"
    assert repo.get_claim(other.claim_id).status == "UNREVIEWED"
    assert repo.list_claims(old_id, "STALE")[0].claim_id == changed.claim_id
    # idempotent: STALE claims are not re-reported
    assert repo.mark_stale_for_changed_evidence(old_id, new_id) == []


def test_staleness_ignores_pure_line_shifts(ncm: NormalizedCodeModel) -> None:
    repo = FakeGraphRepository()
    old_id = repo.load_model(ncm)
    claim = fake_generate_artifact(repo, old_id, "function_card", _id(ncm, "NavMsg_IsValid"))
    repo.save_claim(claim.claims[0].model_copy(update={"status": "EDITED"}))
    shifted = ncm.model_copy(
        update={
            "manifest": ncm.manifest.model_copy(update={"run_id": make_id("shifted")}),
            "evidence": [
                e.model_copy(update={"start_line": e.start_line + 5, "end_line": e.end_line + 5})
                for e in ncm.evidence
            ],
        }
    )
    new_id = repo.load_model(shifted)
    assert repo.mark_stale_for_changed_evidence(old_id, new_id) == []


# --- fakes ------------------------------------------------------------------------------------


def test_fake_run_analysis_variant_and_repo_path() -> None:
    base = fake_run_analysis(Path("some/repo"))
    assert base.manifest.repo_path == "some/repo"
    variant = fake_run_analysis(Path("some/repo"), variant="variant_b")
    assert variant.manifest.variant == "variant_b"
    assert variant.manifest.run_id != base.manifest.run_id


def test_fake_generate_artifact_template_only_with_real_evidence(
    repo: FakeGraphRepository, ncm: NormalizedCodeModel
) -> None:
    run_id = ncm.manifest.run_id
    art = fake_generate_artifact(repo, run_id, "function_card", _id(ncm, "NavTask_Run"))
    assert art.generated_by == "TEMPLATE" and art.validation.passed
    assert 1 <= len(art.claims) <= 2
    assert art.structured["callees"][0] == "NavMsg_Decode"
    for claim in art.claims:
        assert claim.classification == "SUPPORTED" and claim.origin == "TEMPLATE"
        assert claim.status == "UNREVIEWED"
        assert claim.evidence_ids
        assert all(repo.get_evidence(run_id, e) is not None for e in claim.evidence_ids)
    assert "not certification evidence" in art.banner
    tree = fake_generate_artifact(repo, run_id, "call_tree", _id(ncm, "Dispatch_Handle"))
    assert tree.mermaid is not None and "-.->" in tree.mermaid
    with pytest.raises(ValueError):
        fake_generate_artifact(repo, run_id, "function_card", "sha256:nope")


def test_fallback_evidence_is_never_supported(
    repo: FakeGraphRepository, ncm: NormalizedCodeModel
) -> None:
    art = fake_generate_artifact(
        repo, ncm.manifest.run_id, "function_card", _id(ncm, "Display_Refresh")
    )
    assert art.claims and all(c.classification == "INFERRED" for c in art.claims)


def test_fake_compute_impact_for_demo_seed(
    repo: FakeGraphRepository, ncm: NormalizedCodeModel
) -> None:
    run_id = ncm.manifest.run_id
    result = fake_compute_impact(repo, run_id, [_id(ncm, "NavMsg_IsValid")])
    assert [i.name for i in result.direct] == ["NavTask_Run"]
    assert [i.name for i in result.uncertain_frontier] == ["Dispatch_Handle"]
    assert [i.name for i in result.verification] == ["test_NavMsg_IsValid_rejects_stale"]
    assert result.empty_message is None and not result.truncated
    for item in [*result.direct, *result.uncertain_frontier, *result.verification]:
        assert item.path and all(h.evidence_ids for h in item.path)
        assert item.reason
    frontier = result.uncertain_frontier[0]
    assert any(h.edge_type == "MAY_CALL" for h in frontier.path)


def test_fake_compute_impact_empty_uses_fixed_wording(
    repo: FakeGraphRepository, ncm: NormalizedCodeModel
) -> None:
    result = fake_compute_impact(repo, ncm.manifest.run_id, [_id(ncm, "NavMsg_Decode")])
    # NavMsg_Decode is only called by NavTask_Run, so it is not empty; use a node nobody uses.
    assert [i.name for i in result.direct] == ["NavTask_Run"]
    lonely = fake_compute_impact(repo, ncm.manifest.run_id, [_id(ncm, "Dispatch_Handle")])
    assert lonely.empty_message == EMPTY_IMPACT_MESSAGE
    assert "no impact" not in (lonely.empty_message or "").lower()


def test_fake_compute_impact_transitive_and_truncation(
    repo: FakeGraphRepository, ncm: NormalizedCodeModel
) -> None:
    run_id = ncm.manifest.run_id
    # g_nav_state is read by Display_Refresh (direct); Guidance_Step calls it (transitive).
    result = fake_compute_impact(repo, run_id, [_id(ncm, "Display_Refresh")])
    assert [i.name for i in result.direct] == ["Guidance_Step"]
    assert [i.name for i in result.transitive] == ["NavTask_Run"]
    short = fake_compute_impact(
        repo, run_id, [_id(ncm, "Display_Refresh")], TraversalLimits(max_depth=1)
    )
    assert short.truncated and short.truncation_reason


def test_fake_answer(repo: FakeGraphRepository, ncm: NormalizedCodeModel) -> None:
    ans = fake_answer(repo, ncm.manifest.run_id, "What does NavMsg_IsValid do?")
    assert ans.artifact is not None and ans.claims
    assert ans.tool_calls and ans.tool_calls[0]["tool"] == "find_symbols"
    miss = fake_answer(repo, ncm.manifest.run_id, "What about Frobnicate?")
    assert miss.artifact is None and miss.claims == []


# --- stub entry points ------------------------------------------------------------------------


def test_stub_entry_points_chain_together(tmp_path: Path) -> None:
    ncm = run_analysis(tmp_path)
    repo = open_repository(tmp_path / "x.db")
    run_id = repo.load_model(ncm)
    repo.activate(run_id)
    seed = _id(ncm, "NavMsg_IsValid")
    assert compute_impact(repo, run_id, [seed]).direct
    assert generate_artifact(repo, run_id, "function_card", seed).claims
    assert answer(repo, run_id, "NavMsg_IsValid").artifact is not None
