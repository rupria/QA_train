"""Application registry containing the adapters currently shipped."""

from __future__ import annotations

from .common.registry import AdapterRegistry
from .languages.python import PythonAdapter


def default_registry() -> AdapterRegistry:
    return AdapterRegistry([PythonAdapter()])
