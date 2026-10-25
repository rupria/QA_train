"""Contract implemented by each language-specific analyzer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .capabilities import AnalysisCapabilities
from .models import ProjectGraph


class LanguageAdapter(ABC):
    language_id: str
    display_name: str
    extensions: frozenset[str]
    capabilities: AnalysisCapabilities

    def supports_file(self, path: Path) -> bool:
        return Path(path).suffix.lower() in self.extensions

    @abstractmethod
    def analyze(self, source: Path) -> ProjectGraph:
        """Parse one source root without importing or executing target code."""
