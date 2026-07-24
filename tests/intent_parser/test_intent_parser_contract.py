"""Contract test: verify robotsix_llmio.core exports the symbols
intent_parser/__init__.py actually imports at runtime.

This file must NOT mock sys.modules['robotsix_llmio'] or
sys.modules['robotsix_llmio.core'] — the whole point is to hit the
real package and fail loudly if a symbol disappears.

Because test_intent_parser.py installs module-level sys.modules stubs
at import time, the contract tests run in a subprocess to guarantee a
clean Python environment.
"""

from __future__ import annotations

import subprocess
import sys


def _run_contract(code: str) -> subprocess.CompletedProcess[str]:
    """Execute *code* in a clean subprocess and return the result."""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )


def test_build_agent_for_level_is_exported() -> None:
    """build_agent_for_level must be importable from robotsix_llmio.core."""
    result = _run_contract(
        "from robotsix_llmio.core import build_agent_for_level; "
        "assert callable(build_agent_for_level)"
    )
    assert result.returncode == 0, (
        f"build_agent_for_level contract failed:\n{result.stderr}"
    )


def test_run_agent_is_exported() -> None:
    """run_agent must be importable from robotsix_llmio.core."""
    result = _run_contract(
        "from robotsix_llmio.core import run_agent; assert callable(run_agent)"
    )
    assert result.returncode == 0, f"run_agent contract failed:\n{result.stderr}"


def test_get_provider_no_longer_exported() -> None:
    """get_provider was removed; regression guard if it is accidentally re-added.

    If this test starts failing it means llmio re-introduced get_provider —
    update intent_parser/__init__.py to use it again OR keep build_agent_for_level
    (preferred) and delete this guard.
    """
    result = _run_contract(
        "import importlib; core = importlib.import_module('robotsix_llmio.core'); "
        "assert not hasattr(core, 'get_provider'), "
        "'get_provider is back in robotsix_llmio.core'"
    )
    assert result.returncode == 0, (
        f"get_provider contract guard failed:\n{result.stderr}"
    )
