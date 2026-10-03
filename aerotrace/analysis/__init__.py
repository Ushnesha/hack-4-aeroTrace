"""Analysis stream entry point."""

from pathlib import Path

from aerotrace.contracts import NormalizedCodeModel, fake_run_analysis


def run_analysis(
    repo_path: Path, variant: str = "baseline", compile_db: Path | None = None
) -> NormalizedCodeModel:
    """Analyze a C repo into a NormalizedCodeModel (currently returns the sample fake)."""
    # TODO(analysis): replace with real implementation
    return fake_run_analysis(repo_path, variant, compile_db)
