"""Shared fixtures for the end-to-end tests: every test gets its own database and no LLM."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from aerotrace import service

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolated_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point the service at a throwaway database, disable the LLM and ignore any real .env."""
    monkeypatch.setattr(service, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("AEROTRACE_DB", str(tmp_path / ".aerotrace" / "test.db"))
    monkeypatch.setenv("AEROTRACE_LLM_PROVIDER", "disabled")
    service.reset()
    yield
    service.reset()


@pytest.fixture()
def repo_dir(tmp_path: Path) -> Path:
    """An empty folder standing in for the analyzed C repository."""
    path = tmp_path / "repo"
    path.mkdir()
    return path


@pytest.fixture(scope="session")
def sample_script() -> ModuleType:
    """The scripts/make_sample_ncm.py module, used to build a second, edited analysis."""
    spec = importlib.util.spec_from_file_location(
        "make_sample_ncm_e2e", ROOT / "scripts" / "make_sample_ncm.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses in the script look itself up here
    spec.loader.exec_module(module)
    return module
