"""End-to-end tests for aerotrace.service, run against the stub entry points and fakes."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from aerotrace import service
from aerotrace.contracts import Evidence, hash_bytes, load_sample_ncm, make_id

ALLOWED_AEROTRACE_IMPORTS = {
    "aerotrace.analysis",
    "aerotrace.ask",
    "aerotrace.contracts",
    "aerotrace.graph",
    "aerotrace.impact",
    "aerotrace.narrative",
}


def _function_id(run_id: str, name: str) -> str:
    hits = [n for n in service.search(run_id, name, kinds=["Function"]) if n.name == name]
    assert len(hits) == 1, name
    return hits[0].id


def _accept(claim_id: str) -> None:
    repo = service.repository()
    claim = repo.get_claim(claim_id)
    assert claim is not None
    repo.save_claim(claim.model_copy(update={"status": "ACCEPTED"}))


# --- analyze ----------------------------------------------------------------------------------


def test_analyze_loads_activates_and_returns_manifest(repo_dir: Path, tmp_path: Path) -> None:
    manifest = service.analyze(repo_dir)
    repo = service.repository()
    assert repo.active_run_id() == manifest.run_id
    assert manifest.build_context == "PARTIAL"
    assert manifest.repo_path == str(repo_dir)
    assert (tmp_path / ".aerotrace").is_dir()  # parent folder of AEROTRACE_DB was created


def test_analyze_variant_gets_its_own_run(repo_dir: Path) -> None:
    base = service.analyze(repo_dir)
    other = service.analyze(repo_dir, variant="variant_b")
    assert other.variant == "variant_b" and other.run_id != base.run_id
    assert service.repository().active_run_id() == other.run_id


def test_analyze_rejects_missing_folder_and_keeps_active_run(
    repo_dir: Path, tmp_path: Path
) -> None:
    manifest = service.analyze(repo_dir)
    with pytest.raises(FileNotFoundError):
        service.analyze(tmp_path / "does-not-exist")
    assert service.repository().active_run_id() == manifest.run_id


def test_repository_is_cached_per_database_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = service.repository()
    assert service.repository() is first
    monkeypatch.setenv("AEROTRACE_DB", str(tmp_path / "other.db"))
    assert service.repository() is not first


def test_db_path_defaults_when_unset_or_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROTRACE_DB")
    assert service.db_path() == Path(service.DEFAULT_DB)
    monkeypatch.setenv("AEROTRACE_DB", "")
    assert service.db_path() == Path(".aerotrace/aerotrace.db")


# --- overview and search ----------------------------------------------------------------------


def test_overview(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    data = service.overview(run_id)
    assert data["run_id"] == run_id
    assert data["manifest"]["run_id"] == run_id
    assert data["build_context"] == "PARTIAL"
    assert data["coverage_counts"] == {
        "PARSED": 6,
        "FALLBACK_PARSED": 1,
        "FAILED": 1,
        "SKIPPED": 0,
    }
    assert data["unresolved_call_count"] == 1
    assert any("unresolved callback" in gap for gap in data["known_gaps"])
    json.dumps(data)  # must be JSON-friendly for the API


def test_overview_unknown_run_raises() -> None:
    with pytest.raises(KeyError):
        service.overview("sha256:nope")


def test_search(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    assert [n.name for n in service.search(run_id, "navtask_run")] == ["NavTask_Run"]
    assert service.search(run_id, "") == []
    assert [n.name for n in service.search(run_id, "nav", kinds=["Variable"])] == ["g_nav_state"]
    assert len(service.search(run_id, "nav", limit=2)) == 2


# --- artifacts, impact, ask -------------------------------------------------------------------


def test_artifact_is_template_only_stored_and_reviewable(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    subject = _function_id(run_id, "NavMsg_IsValid")
    art = service.artifact(run_id, "function_card", subject)
    assert art.generated_by == "TEMPLATE" and art.claims
    repo = service.repository()
    assert repo.get_artifact(art.artifact_id) == art
    assert all(repo.get_claim(c.claim_id) == c for c in art.claims)


@pytest.mark.parametrize(
    ("provider", "requested", "expected"),
    [
        ("disabled", True, False),
        ("", True, False),
        ("anthropic", True, True),
        ("ANTHROPIC", True, True),
        ("anthropic", False, False),
    ],
)
def test_llm_is_used_only_when_enabled_and_requested(
    monkeypatch: pytest.MonkeyPatch, repo_dir: Path, provider: str, requested: bool, expected: bool
) -> None:
    run_id = service.analyze(repo_dir).run_id
    subject = _function_id(run_id, "NavTask_Run")
    monkeypatch.setenv("AEROTRACE_LLM_PROVIDER", provider)
    seen: list[bool] = []
    real = service.generate_artifact

    def spy(repo, run_id, kind, subject_id, use_llm=True):
        seen.append(use_llm)
        return real(repo, run_id, kind, subject_id, use_llm)

    monkeypatch.setattr(service, "generate_artifact", spy)
    service.artifact(run_id, "function_card", subject, use_llm=requested)
    assert seen == [expected]


def test_regenerating_an_artifact_keeps_reviewed_claims(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    subject = _function_id(run_id, "NavMsg_IsValid")
    first = service.artifact(run_id, "function_card", subject)
    _accept(first.claims[0].claim_id)
    again = service.artifact(run_id, "function_card", subject)
    assert again.claims[0].status == "ACCEPTED"
    stored = service.repository().get_claim(first.claims[0].claim_id)
    assert stored is not None and stored.status == "ACCEPTED"


def test_impact_for_the_demo_seed(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    result = service.impact(run_id, [_function_id(run_id, "NavMsg_IsValid")])
    assert [i.name for i in result.direct] == ["NavTask_Run"]
    assert [i.name for i in result.uncertain_frontier] == ["Dispatch_Handle"]
    assert result.verification


def test_impact_requires_a_seed(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    with pytest.raises(ValueError):
        service.impact(run_id, [])


def test_ask_stores_claims_and_keeps_reviewed_ones(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    reply = service.ask(run_id, "  What does NavMsg_IsValid do?  ")
    assert reply.question == "What does NavMsg_IsValid do?"
    assert reply.artifact is not None and reply.claims
    repo = service.repository()
    assert all(repo.get_claim(c.claim_id) == c for c in reply.claims)
    _accept(reply.claims[0].claim_id)
    again = service.ask(run_id, "What does NavMsg_IsValid do?")
    assert again.claims[0].status == "ACCEPTED"
    assert again.artifact is not None and again.artifact.claims[0].status == "ACCEPTED"


def test_ask_without_a_match_has_no_artifact(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    reply = service.ask(run_id, "What about Frobnicate?")
    assert reply.artifact is None and reply.claims == []


def test_ask_rejects_a_blank_question(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    with pytest.raises(ValueError):
        service.ask(run_id, "   ")


# --- evidence ---------------------------------------------------------------------------------


def _load_with_evidence(
    repo_dir: Path, rel: str, data: bytes, start: int, end: int, write: bool = True
) -> tuple[str, str]:
    """Load the sample plus one extra evidence span over a real file; return (run_id, ev_id)."""
    if write:
        path = repo_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    ev = Evidence(
        evidence_id=make_id("e2e", rel, str(start), str(end)),
        file=rel,
        start_line=1,
        end_line=1,
        start_byte=start,
        end_byte=end,
        snippet_hash=hash_bytes(data[start:end]),
        analysis_method="clang",
        quality="PRECISE",
    )
    ncm = load_sample_ncm()
    ncm = ncm.model_copy(
        update={
            "evidence": [*ncm.evidence, ev],
            "manifest": ncm.manifest.model_copy(update={"repo_path": str(repo_dir)}),
        }
    )
    repo = service.repository()
    run_id = repo.load_model(ncm)
    repo.activate(run_id)
    return run_id, ev.evidence_id


def test_evidence_shows_the_span_with_context(repo_dir: Path) -> None:
    body = b"int f(void)\n{\n    return g();\n}\n"
    prefix = b"/* a */\n/* b */\n/* c */\n/* d */\n"
    data = prefix + body + b"/* t1 */\n/* t2 */\n/* t3 */\n"
    start, end = len(prefix), len(prefix) + len(body) - 1  # exclude the final newline
    run_id, ev_id = _load_with_evidence(repo_dir, "src/f.c", data, start, end)
    out = service.evidence(run_id, ev_id)
    assert out["status"] == "OK" and out["hash_ok"] is True
    assert out["evidence"]["evidence_id"] == ev_id
    lines = out["source_lines"]
    assert [ln["line"] for ln in lines] == list(range(3, 11))  # span is lines 5-8, 2 lines context
    assert [ln["text"] for ln in lines if ln["in_span"]] == [
        "int f(void)",
        "{",
        "    return g();",
        "}",
    ]
    assert [ln["line"] for ln in lines if ln["in_span"]] == [5, 6, 7, 8]


def test_evidence_span_ending_in_newline_covers_only_its_own_line(repo_dir: Path) -> None:
    data = b"one\ntwo\nthree\n"
    run_id, ev_id = _load_with_evidence(repo_dir, "a.c", data, 4, 8)  # b"two\n"
    lines = service.evidence(run_id, ev_id)["source_lines"]
    assert [ln["line"] for ln in lines if ln["in_span"]] == [2]
    assert [ln["text"] for ln in lines] == ["one", "two", "three", ""]


def test_evidence_handles_crlf_files(repo_dir: Path) -> None:
    data = b"int a;\r\nint b;\r\nint c;\r\n"
    run_id, ev_id = _load_with_evidence(repo_dir, "a.c", data, 8, 14)  # b"int b;"
    lines = service.evidence(run_id, ev_id)["source_lines"]
    assert [ln["text"] for ln in lines][:3] == ["int a;", "int b;", "int c;"]
    assert [ln["line"] for ln in lines if ln["in_span"]] == [2]


def test_evidence_handles_non_ascii_source(repo_dir: Path) -> None:
    data = "// α\nint café = 1;\n".encode()
    start = data.index(b"int")
    run_id, ev_id = _load_with_evidence(repo_dir, "a.c", data, start, len(data) - 1)
    lines = service.evidence(run_id, ev_id)["source_lines"]
    assert [ln["text"] for ln in lines if ln["in_span"]] == ["int café = 1;"]


def test_evidence_flags_drift_instead_of_showing_changed_code(repo_dir: Path) -> None:
    data = b"int limit = 100;\n"
    run_id, ev_id = _load_with_evidence(repo_dir, "a.c", data, 0, 15)
    (repo_dir / "a.c").write_bytes(b"int limit = 999;\n")  # same length, different content
    out = service.evidence(run_id, ev_id)
    assert out["status"] == "HASH_MISMATCH" and out["hash_ok"] is False
    assert out["source_lines"] is None
    assert "999" not in json.dumps(out)
    assert "Re-run analysis" in out["message"]


def test_evidence_does_not_relocate_a_shifted_span(repo_dir: Path) -> None:
    run_id, ev_id = _load_with_evidence(repo_dir, "a.c", b"int a;\nint b;\n", 7, 13)
    (repo_dir / "a.c").write_bytes(b"/* new */\nint a;\nint b;\n")  # a line was inserted above
    out = service.evidence(run_id, ev_id)
    assert out["status"] == "HASH_MISMATCH" and out["source_lines"] is None


def test_evidence_flags_missing_and_truncated_files(repo_dir: Path) -> None:
    run_id, ev_id = _load_with_evidence(repo_dir, "a.c", b"int a;\nint b;\n", 7, 13)
    (repo_dir / "a.c").write_bytes(b"int a;")  # shorter than the span
    assert service.evidence(run_id, ev_id)["status"] == "SPAN_OUT_OF_RANGE"
    (repo_dir / "a.c").unlink()
    out = service.evidence(run_id, ev_id)
    assert out["status"] == "FILE_MISSING" and out["source_lines"] is None


@pytest.mark.parametrize("rel", ["../outside.c", "/etc/hosts", "src/../../outside.c"])
def test_evidence_refuses_paths_outside_the_repo(repo_dir: Path, rel: str) -> None:
    run_id, ev_id = _load_with_evidence(repo_dir, rel, b"secret\n", 0, 6, write=False)
    (repo_dir.parent / "outside.c").write_bytes(b"secret\n")
    out = service.evidence(run_id, ev_id)
    assert out["status"] == "PATH_OUTSIDE_REPO" and out["source_lines"] is None
    assert "secret" not in json.dumps(out)


def test_evidence_unknown_id_raises(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    with pytest.raises(service.NotFoundError):
        service.evidence(run_id, "sha256:nope")


def test_evidence_for_the_sample_run_is_flagged_not_invented(repo_dir: Path) -> None:
    """The sample's spans do not exist in an empty repo, so nothing may be shown."""
    run_id = service.analyze(repo_dir).run_id
    node = service.search(run_id, "NavMsg_IsValid", kinds=["Function"])[0]
    out = service.evidence(run_id, node.evidence_ids[0])
    assert out["status"] == "FILE_MISSING" and out["source_lines"] is None


# --- reanalyze --------------------------------------------------------------------------------


def test_reanalyze_with_no_earlier_run(repo_dir: Path) -> None:
    out = service.reanalyze(repo_dir)
    assert out["old_run_id"] is None and out["stale_claim_ids"] == []
    assert out["new_run_id"] == service.repository().active_run_id()


def test_reanalyze_of_an_unchanged_repo_marks_nothing_stale(repo_dir: Path) -> None:
    run_id = service.analyze(repo_dir).run_id
    claim = service.artifact(run_id, "function_card", _function_id(run_id, "NavMsg_IsValid"))
    _accept(claim.claims[0].claim_id)
    out = service.reanalyze(repo_dir)
    assert out["old_run_id"] == out["new_run_id"] == run_id
    assert out["stale_claim_ids"] == []


def test_reanalyze_marks_only_changed_reviewed_claims_stale(
    monkeypatch: pytest.MonkeyPatch, repo_dir: Path, sample_script: ModuleType
) -> None:
    old_run = service.analyze(repo_dir).run_id
    changed = service.artifact(old_run, "function_card", _function_id(old_run, "NavMsg_IsValid"))
    untouched = service.artifact(old_run, "function_card", _function_id(old_run, "NavState_Update"))
    unreviewed = service.artifact(old_run, "call_tree", _function_id(old_run, "NavMsg_IsValid"))
    _accept(changed.claims[0].claim_id)
    _accept(untouched.claims[0].claim_id)

    edited = sample_script.build_sample_ncm(
        commit="c" * 40,
        snippet_overrides={"def:NavMsg_IsValid": "bool NavMsg_IsValid(...) { /* edited */ }"},
    )
    monkeypatch.setattr(service, "run_analysis", lambda root, variant="baseline": edited)

    out = service.reanalyze(repo_dir)
    repo = service.repository()
    assert out["old_run_id"] == old_run
    assert out["new_run_id"] == edited.manifest.run_id != old_run
    assert repo.active_run_id() == out["new_run_id"]
    assert out["stale_claim_ids"] == [changed.claims[0].claim_id]
    assert repo.get_claim(changed.claims[0].claim_id).status == "STALE"
    assert repo.get_claim(untouched.claims[0].claim_id).status == "ACCEPTED"
    assert repo.get_claim(unreviewed.claims[0].claim_id).status == "UNREVIEWED"


def test_failed_reanalysis_keeps_the_previous_run_active(
    monkeypatch: pytest.MonkeyPatch, repo_dir: Path
) -> None:
    run_id = service.analyze(repo_dir).run_id

    def boom(root: Path, variant: str = "baseline"):
        raise RuntimeError("analysis failed")

    monkeypatch.setattr(service, "run_analysis", boom)
    with pytest.raises(RuntimeError):
        service.reanalyze(repo_dir)
    assert service.repository().active_run_id() == run_id


# --- rules from CLAUDE.md ---------------------------------------------------------------------


def test_service_only_imports_contract_entry_points() -> None:
    tree = ast.parse(Path(service.__file__).read_text(encoding="utf-8"))
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("aerotrace")
    }
    assert imported <= ALLOWED_AEROTRACE_IMPORTS, imported - ALLOWED_AEROTRACE_IMPORTS


def test_service_never_runs_processes_or_uses_banned_wording() -> None:
    source = Path(service.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\b(subprocess|os\.system|shell=True|eval|exec)\b", source)
    assert not re.search(r"\b(safe|safely|certified|compliant|no impact)\b", source, re.IGNORECASE)
