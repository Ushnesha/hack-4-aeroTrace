"""Graph stream entry point."""

from pathlib import Path

from aerotrace.contracts import FakeGraphRepository, GraphRepository


def open_repository(db_path: Path) -> GraphRepository:
    """Open the graph repository at ``db_path`` (currently an in-memory fake; path ignored)."""
    # TODO(graph): replace with real implementation
    return FakeGraphRepository()
