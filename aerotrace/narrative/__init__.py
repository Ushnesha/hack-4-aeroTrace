"""Narrative stream entry point."""

from typing import cast

from aerotrace.contracts import (
    Artifact,
    ArtifactKind,
    FakeGraphRepository,
    GraphRepository,
    fake_generate_artifact,
)


def generate_artifact(
    repo: GraphRepository,
    run_id: str,
    kind: ArtifactKind,
    subject_id: str,
    use_llm: bool = True,
) -> Artifact:
    """Generate an artifact for ``subject_id`` (currently the template-only fake)."""
    # TODO(narrative): replace with real implementation
    return fake_generate_artifact(
        cast(FakeGraphRepository, repo), run_id, kind, subject_id, use_llm
    )
