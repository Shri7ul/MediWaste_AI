# tests/conftest.py — make the project root importable under pytest, and give
# every test a deterministic, isolated audit/collection database.
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import audit_store  # noqa: E402  (import after ROOT is on sys.path)


@pytest.fixture(autouse=True)
def _isolated_audit_db():
    """Reset audit_store to a fresh, empty SQLite file before EACH test.

    Root cause of the prior cross-test failures: ``audit_store.DB_PATH`` is a
    single process-global that ``_connect()`` reads on every call. Multiple test
    modules reassigned it only at import time, so under pytest the last-imported
    module won and ALL tests shared one accumulating database. Leftover audit
    events and collection jobs then leaked between tests (empty bins were not
    empty, active jobs already existed, item counts were inflated).

    Isolating per test gives deterministic state (Prompt 07 acceptance A/C/E)
    without weakening any production behaviour — the reset only swaps the DB
    file the store points at; no assertion or domain rule is changed.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    audit_store.DB_PATH = tmp.name
    audit_store.init_db()
    try:
        yield
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
