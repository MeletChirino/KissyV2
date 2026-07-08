"""Smoke test: proves the toolchain can build and import the package.

This is intentionally trivial. Its only job is to fail loudly if:
- `uv sync` did not install the runtime dependencies, or
- the `src/` layout is not on `sys.path` for pytest, or
- the package itself fails to import for any reason (syntax error, missing
  `__init__.py`, etc.).

Once this passes, you know `uv run pytest` is wired correctly and every
future test file can be added with confidence.
"""

from __future__ import annotations


def test_package_imports() -> None:
    """The `telegram_bot` package must import without errors."""
    import telegram_bot  # noqa: F401


def test_entry_point_module_exists() -> None:
    """`python -m telegram_bot` must be runnable, so `__main__.py` must exist."""
    from importlib import util

    spec = util.find_spec("telegram_bot.__main__")
    assert spec is not None, "telegram_bot.__main__ module not found"
