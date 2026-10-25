"""Registry for explicit user-selected language adapters."""

from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path

from .adapter import LanguageAdapter


class AdapterRegistry:
    DEFAULT_IGNORED_DIRS = frozenset({
        ".git", ".venv", ".venv-ast", "__pycache__", ".pytest_cache",
        ".mypy_cache", ".ruff_cache", "node_modules", "build", "dist",
    })

    def __init__(self, adapters: Iterable[LanguageAdapter] = ()) -> None:
        self._adapters: dict[str, LanguageAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: LanguageAdapter) -> None:
        language_id = adapter.language_id.strip().lower()
        if not language_id:
            raise ValueError("adapter language_id is required")
        if language_id in self._adapters:
            raise ValueError(f"language adapter already registered: {language_id}")
        self._adapters[language_id] = adapter

    def get(self, language_id: str) -> LanguageAdapter:
        key = language_id.strip().lower()
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise KeyError(f"unsupported language adapter: {language_id}") from exc

    def selected(self, language_ids: Iterable[str]) -> list[LanguageAdapter]:
        selected: list[LanguageAdapter] = []
        seen: set[str] = set()
        for language_id in language_ids:
            key = language_id.strip().lower()
            if key and key not in seen:
                selected.append(self.get(key))
                seen.add(key)
        if not selected:
            raise ValueError("select at least one language adapter")
        return selected

    def detect(self, root: Path) -> dict[str, int]:
        """Return extension evidence for UI suggestions; users still confirm selection."""
        root = Path(root)
        counts = {language_id: 0 for language_id in self._adapters}
        for path in self._source_files(root):
            for language_id, adapter in self._adapters.items():
                if adapter.supports_file(path):
                    counts[language_id] += 1
        return {key: value for key, value in counts.items() if value}

    def _source_files(self, root: Path):
        if root.is_file():
            yield root
            return
        if not root.is_dir():
            raise FileNotFoundError(f"source root does not exist: {root}")
        for directory, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in self.DEFAULT_IGNORED_DIRS)
            for name in sorted(names):
                yield Path(directory) / name

    def descriptors(self) -> list[dict]:
        return [
            {
                "id": key,
                "name": adapter.display_name,
                "extensions": sorted(adapter.extensions),
                "capabilities": adapter.capabilities.to_dict(),
            }
            for key, adapter in sorted(self._adapters.items())
        ]
