"""AeroTrace backend entry point.

Run with ``make api`` or ``python -m aerotrace.api.main``.
"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

app = FastAPI(title="AeroTrace", description="Read-only, evidence-first code analysis API.")

# TODO: add routes that call `aerotrace.service` (never other streams' private modules).


@app.get("/health")
def health() -> dict[str, str]:
    """Return a liveness payload. Never fails unless the process is down."""
    return {"status": "ok", "service": "aerotrace"}


def main() -> None:
    """Start the API server. Host and port come from AEROTRACE_HOST / AEROTRACE_PORT."""
    host = os.environ.get("AEROTRACE_HOST", "127.0.0.1")
    port = int(os.environ.get("AEROTRACE_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
