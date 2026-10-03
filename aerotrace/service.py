"""Application service layer: the one place the UI, CLI and API call into AeroTrace.

Only the entry points in docs/CONTRACTS.md and the types in ``aerotrace.contracts`` are used.
Nothing here parses code, builds graph edges or writes narrative text.

Configuration comes from the environment (a ``.env`` file is loaded if present):
``AEROTRACE_DB`` (default ``.aerotrace/aerotrace.db``) and ``AEROTRACE_LLM_PROVIDER``
(``disabled`` | ``anthropic``; anything but ``anthropic`` means templates only).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from aerotrace.analysis import run_analysis
from aerotrace.ask import answer
from aerotrace.contracts import (
    Artifact,
    ArtifactKind,
    AskAnswer,
    Claim,
    Evidence,
    FileStatus,
    GraphRepository,
    ImpactResult,
    Node,
    NodeKind,
    RunManifest,
    hash_bytes,
)
from aerotrace.graph import open_repository
from aerotrace.impact import compute_impact
from aerotrace.narrative import generate_artifact

__all__ = [
    "DEFAULT_DB",
    "NotFoundError",
    "analyze",
    "artifact",
    "ask",
    "db_path",
    "evidence",
    "impact",
    "llm_enabled",
    "overview",
    "reanalyze",
    "repository",
    "reset",
    "search",
]

DEFAULT_DB = ".aerotrace/aerotrace.db"

_FILE_STATUSES: tuple[FileStatus, ...] = ("PARSED", "FALLBACK_PARSED", "FAILED", "SKIPPED")
_CONTEXT_LINES = 2  # lines of source shown before and after an evidence span
_MAX_LISTED_SYMBOLS = 100_000

_repositories: dict[Path, GraphRepository] = {}


class NotFoundError(LookupError):
    """Raised when a requested run object (for example an evidence id) does not exist."""


# --- configuration and repository handle ------------------------------------------------------


def _load_env() -> None:
    load_dotenv()  # never overrides variables that are already set


def db_path() -> Path:
    """Return the graph database path from ``AEROTRACE_DB`` (default ``.aerotrace/aerotrace.db``)."""
    _load_env()
    return Path(os.environ.get("AEROTRACE_DB") or DEFAULT_DB)


def llm_enabled() -> bool:
    """Return True only if ``AEROTRACE_LLM_PROVIDER`` is ``anthropic``; otherwise templates only."""
    _load_env()
    return os.environ.get("AEROTRACE_LLM_PROVIDER", "disabled").strip().lower() == "anthropic"


def repository() -> GraphRepository:
    """Return the shared repository for the configured database, opening it on first use.

    The handle is cached per database path so state survives between service calls even when
    the repository is in-memory (the stub). Creates the database's parent folder if needed.
    """
    path = db_path()
    key = path.resolve()
    repo = _repositories.get(key)
    if repo is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        repo = open_repository(path)
        _repositories[key] = repo
    return repo


def reset() -> None:
    """Forget every cached repository handle (used by tests and after changing ``AEROTRACE_DB``)."""
    _repositories.clear()


# --- analysis ---------------------------------------------------------------------------------


def analyze(repo_path: str | Path, variant: str = "baseline") -> RunManifest:
    """Analyze ``repo_path`` and make the result the active run.

    Runs ``run_analysis``, then ``load_model`` and ``activate`` on the configured repository.
    Returns the new run's manifest. Raises FileNotFoundError if ``repo_path`` is not a folder;
    errors from analysis or activation (for example a model that fails validation) propagate
    and leave the previously active run untouched.
    """
    root = Path(repo_path)
    if not root.is_dir():
        raise FileNotFoundError(f"repository path is not a folder: {root}")
    ncm = run_analysis(root, variant)
    repo = repository()
    run_id = repo.load_model(ncm)
    repo.activate(run_id)
    return repo.get_manifest(run_id)


def reanalyze(repo_path: str | Path, variant: str = "baseline") -> dict[str, Any]:
    """Analyze again, then mark reviewed claims whose cited evidence changed as STALE.

    Returns ``{"new_run_id", "old_run_id", "stale_claim_ids"}``. ``old_run_id`` is the run that
    was active before (None if there was none); with no earlier run, or when the new run has the
    same run_id as the old one, nothing can be compared and ``stale_claim_ids`` is empty.
    """
    repo = repository()
    old_run_id = repo.active_run_id()
    manifest = analyze(repo_path, variant)
    stale: list[str] = []
    if old_run_id is not None and old_run_id != manifest.run_id:
        stale = repo.mark_stale_for_changed_evidence(old_run_id, manifest.run_id)
    return {
        "new_run_id": manifest.run_id,
        "old_run_id": old_run_id,
        "stale_claim_ids": stale,
    }


# --- reads ------------------------------------------------------------------------------------


def overview(run_id: str) -> dict[str, Any]:
    """Summarize a run: manifest, build-context state, file coverage, gaps and unresolved calls.

    Returns a JSON-friendly dict with keys ``run_id``, ``manifest``, ``build_context``,
    ``coverage_counts`` (PARSED / FALLBACK_PARSED / FAILED / SKIPPED, zeros included),
    ``unresolved_call_count`` and ``known_gaps``. Raises KeyError-style errors from the
    repository for an unknown run.
    """
    repo = repository()
    manifest = repo.get_manifest(run_id)
    counts: dict[str, int] = dict.fromkeys(_FILE_STATUSES, 0)
    for item in repo.get_coverage(run_id):
        counts[item.status] += 1
    return {
        "run_id": run_id,
        "manifest": manifest.model_dump(mode="json"),
        "build_context": manifest.build_context,
        "coverage_counts": counts,
        "unresolved_call_count": _unresolved_call_count(repo, run_id),
        "known_gaps": repo.get_known_gaps(run_id),
    }


def _unresolved_call_count(repo: GraphRepository, run_id: str) -> int:
    """Count UNRESOLVED_CALL edges (each targets an ExternalSymbol node)."""
    externals = repo.find_symbols(run_id, "", kinds=["ExternalSymbol"], limit=_MAX_LISTED_SYMBOLS)
    return sum(len(repo.edges_to(run_id, node.id, ["UNRESOLVED_CALL"])) for node in externals)


def search(run_id: str, q: str, kinds: list[NodeKind] | None = None, limit: int = 20) -> list[Node]:
    """Find symbols by name in a run. Returns at most ``limit`` nodes; blank ``q`` gives none
    unless ``kinds`` is given (then every symbol of those kinds)."""
    return repository().find_symbols(run_id, q, kinds, limit)


def evidence(run_id: str, evidence_id: str) -> dict[str, Any]:
    """Return an evidence record plus the matching source lines, verified against the file.

    Reads the file from the analyzed repository (``manifest.repo_path``), re-hashes the exact byte
    span and compares it with the stored ``snippet_hash``. Only a matching span is shown, as
    ``source_lines`` (the span plus two lines of context, each ``{"line", "text", "in_span"}``).
    On any problem ``source_lines`` is None and ``status`` says why:
    ``HASH_MISMATCH`` (file changed since analysis), ``FILE_MISSING``, ``SPAN_OUT_OF_RANGE``,
    ``PATH_OUTSIDE_REPO`` or ``UNREADABLE``. Returns ``{"evidence", "source_lines", "status",
    "hash_ok", "message"}``. Raises NotFoundError if the evidence id is not in the run.
    """
    repo = repository()
    ev = repo.get_evidence(run_id, evidence_id)
    if ev is None:
        raise NotFoundError(f"evidence {evidence_id} not found in run {run_id}")
    root = Path(repo.get_manifest(run_id).repo_path).resolve()

    def result(
        status: str, message: str, lines: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        return {
            "evidence": ev.model_dump(mode="json"),
            "source_lines": lines,
            "status": status,
            "hash_ok": status == "OK",
            "message": message,
        }

    path = (root / ev.file).resolve()
    if not path.is_relative_to(root):
        return result("PATH_OUTSIDE_REPO", f"{ev.file} resolves outside the analyzed repository.")
    if not path.is_file():
        return result("FILE_MISSING", f"{ev.file} no longer exists in the analyzed repository.")
    try:
        data = path.read_bytes()
    except OSError as exc:
        return result("UNREADABLE", f"{ev.file} could not be read: {exc.strerror or exc}.")
    if not 0 <= ev.start_byte <= ev.end_byte <= len(data):
        return result(
            "SPAN_OUT_OF_RANGE",
            f"{ev.file} is shorter than the evidence span; it changed since analysis.",
        )
    if hash_bytes(data[ev.start_byte : ev.end_byte]) != ev.snippet_hash:
        return result(
            "HASH_MISMATCH",
            f"{ev.file} changed since analysis; the cited span no longer matches. "
            "Re-run analysis before relying on this evidence.",
        )
    return result("OK", "Source matches the analyzed evidence.", _source_lines(data, ev))


def _source_lines(data: bytes, ev: Evidence) -> list[dict[str, Any]]:
    """Lines of ``data`` covering the evidence span, located from its byte offsets."""
    first = data.count(b"\n", 0, ev.start_byte) + 1
    last = first + data.count(b"\n", ev.start_byte, max(ev.start_byte, ev.end_byte - 1))
    lines = data.split(b"\n")
    lo, hi = max(1, first - _CONTEXT_LINES), min(len(lines), last + _CONTEXT_LINES)
    return [
        {
            "line": n,
            "text": lines[n - 1].rstrip(b"\r").decode("utf-8", errors="replace"),
            "in_span": first <= n <= last,
        }
        for n in range(lo, hi + 1)
    ]


# --- generation -------------------------------------------------------------------------------


def _keep_reviewed(repo: GraphRepository, claims: list[Claim]) -> list[Claim]:
    """Swap in the stored version of any claim a human already acted on.

    Regenerating deterministic output reuses claim ids, so without this a fresh UNREVIEWED copy
    would overwrite an ACCEPTED / EDITED / REJECTED claim.
    """
    kept: list[Claim] = []
    for claim in claims:
        stored = repo.get_claim(claim.claim_id)
        kept.append(stored if stored is not None and stored.status != "UNREVIEWED" else claim)
    return kept


def artifact(run_id: str, kind: ArtifactKind, subject_id: str, use_llm: bool = True) -> Artifact:
    """Generate an artifact for ``subject_id``, store it with its claims, and return it.

    The LLM is used only if ``use_llm`` is true and ``AEROTRACE_LLM_PROVIDER=anthropic``.
    Claims a reviewer already acted on keep their stored status and text.
    """
    repo = repository()
    generated = generate_artifact(repo, run_id, kind, subject_id, use_llm=use_llm and llm_enabled())
    stored = generated.model_copy(update={"claims": _keep_reviewed(repo, generated.claims)})
    repo.save_artifact(stored)
    return stored


def impact(run_id: str, seed_ids: list[str]) -> ImpactResult:
    """Compute grouped change impact (direct, transitive, verification, uncertain frontier).

    Raises ValueError if ``seed_ids`` is empty.
    """
    if not seed_ids:
        raise ValueError("at least one seed id is required")
    return compute_impact(repository(), run_id, list(seed_ids))


def ask(run_id: str, question: str) -> AskAnswer:
    """Answer a question with the typed graph tools, storing any claims so they can be reviewed.

    Raises ValueError if the question is blank. Claims a reviewer already acted on keep their
    stored status and text.
    """
    question = question.strip()
    if not question:
        raise ValueError("question must not be blank")
    repo = repository()
    reply = answer(repo, run_id, question)
    claims = _keep_reviewed(repo, reply.claims)
    stored_artifact = reply.artifact
    if stored_artifact is not None:
        stored_artifact = stored_artifact.model_copy(
            update={"claims": _keep_reviewed(repo, stored_artifact.claims)}
        )
        repo.save_artifact(stored_artifact)
    for claim in claims:
        repo.save_claim(claim)
    return reply.model_copy(update={"artifact": stored_artifact, "claims": claims})
