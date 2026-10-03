"""Impact stream entry point."""

from typing import cast

from aerotrace.contracts import (
    FakeGraphRepository,
    GraphRepository,
    ImpactResult,
    TraversalLimits,
    fake_compute_impact,
)


def compute_impact(
    repo: GraphRepository,
    run_id: str,
    seed_ids: list[str],
    limits: TraversalLimits | None = None,
) -> ImpactResult:
    """Compute grouped change impact for ``seed_ids`` (currently the fake)."""
    # TODO(graph): replace with real implementation
    return fake_compute_impact(cast(FakeGraphRepository, repo), run_id, seed_ids, limits)
