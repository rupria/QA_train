"""Application registry containing the adapters currently shipped."""

from __future__ import annotations

from functools import cache

from .common.registry import AdapterRegistry


@cache
def default_registry() -> AdapterRegistry:
    """Return the process-wide immutable-in-practice adapter catalog."""
    from .languages.python import PythonAdapter
    from .languages.tree_sitter import SPECS, TreeSitterAdapter

    return AdapterRegistry([PythonAdapter(), *(TreeSitterAdapter(spec) for spec in SPECS)])
