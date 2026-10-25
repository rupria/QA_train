"""Application registry containing the adapters currently shipped."""

from __future__ import annotations

from .common.registry import AdapterRegistry
from .languages.python import PythonAdapter
from .languages.tree_sitter import SPECS, TreeSitterAdapter


def default_registry() -> AdapterRegistry:
    return AdapterRegistry([PythonAdapter(), *(TreeSitterAdapter(spec) for spec in SPECS)])
