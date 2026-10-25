"""Shared, language-neutral analysis types."""

from .adapter import LanguageAdapter
from .capabilities import AnalysisCapabilities
from .models import (
    AnalysisBoundary,
    Change,
    CommonEdge,
    CommonNode,
    EdgeKind,
    Evidence,
    ImpactResult,
    NodeKind,
    ProjectGraph,
    Resolution,
    SourceRange,
)
from .registry import AdapterRegistry

__all__ = [
    "AdapterRegistry",
    "AnalysisBoundary",
    "AnalysisCapabilities",
    "Change",
    "CommonEdge",
    "CommonNode",
    "EdgeKind",
    "Evidence",
    "ImpactResult",
    "LanguageAdapter",
    "NodeKind",
    "ProjectGraph",
    "Resolution",
    "SourceRange",
]
