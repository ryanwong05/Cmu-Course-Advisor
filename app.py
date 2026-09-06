"""Stable ASGI entry point for local development and deployment.

Run with: uvicorn app:app --reload

The application implementation lives under Backend. Re-exporting its public
names keeps existing tests and older Python callers compatible while the
frontend continues to use the same HTTP endpoints.
"""

from Backend.application import *  # noqa: F401,F403
