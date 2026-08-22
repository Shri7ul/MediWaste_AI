#!/usr/bin/env python3
# tests/run_offline.py
"""
Dependency-free offline test runner.

Executes the deterministic-core test suite WITHOUT requiring pytest, so the
policy / ontology / pipeline / rag / llm / audit contracts can be validated in a
minimal environment (stdlib + whatever the modules under test already need).

Test files that require optional dependencies (e.g. test_api.py needs Flask and
pytest) are skipped with a clear reason instead of failing. Test functions that
declare required arguments (pytest fixtures) are likewise skipped.

Usage:
    python tests/run_offline.py

Exit code is non-zero if any runnable test fails or errors.
"""

import importlib.util
import inspect
import os
import sys
import traceback

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_module(path):
    name = "offlinetest_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # may raise (e.g. ImportError) -> caller handles
    return mod


def _runnable_tests(mod):
    """Yield (name, callable_or_None, skip_reason_or_None) for each test_*."""
    out = []
    for name, fn in sorted(vars(mod).items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        required = [
            p for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY, p.KEYWORD_ONLY)
        ]
        if required:
            out.append((name, None, "needs fixture/args"))
        else:
            out.append((name, fn, None))
    return out


def main():
    files = sorted(
        os.path.join(TESTS_DIR, f)
        for f in os.listdir(TESTS_DIR)
        if f.startswith("test_") and f.endswith(".py")
    )

    passed = failed = errored = skipped = 0
    failures = []

    for path in files:
        base = os.path.basename(path)
        try:
            mod = _load_module(path)
        except Exception as e:
            skipped += 1
            print(f"SKIP  {base}  (cannot import: {type(e).__name__}: {str(e)[:80]})")
            continue

        tests = _runnable_tests(mod)
        if not tests:
            print(f"----  {base}  (no runnable tests)")
            continue

        print(f"\n# {base}")
        for name, fn, skip_reason in tests:
            if skip_reason:
                skipped += 1
                print(f"  SKIP  {name}  ({skip_reason})")
                continue
            try:
                fn()
                passed += 1
                print(f"  PASS  {name}")
            except AssertionError as e:
                failed += 1
                failures.append((base, name, "AssertionError: " + str(e)))
                print(f"  FAIL  {name}: {str(e)[:120]}")
            except Exception as e:  # noqa: BLE001
                errored += 1
                failures.append((base, name, traceback.format_exc()))
                print(f"  ERROR {name}: {type(e).__name__}: {str(e)[:120]}")

    print("\n" + "=" * 60)
    print(f"passed={passed} failed={failed} errored={errored} skipped={skipped}")
    if failures:
        print("-" * 60)
        for base, name, detail in failures:
            print(f"\n[{base}::{name}]\n{detail}")
    print("=" * 60)
    sys.exit(0 if (failed == 0 and errored == 0) else 1)


if __name__ == "__main__":
    main()
