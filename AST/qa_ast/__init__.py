"""Language-neutral QA analysis contracts and language adapter registry."""

from .common.adapter import LanguageAdapter
from .common.models import (
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
from .registry import default_registry
from .comparison import build_language_comparison, merge_comparison_reports

__all__ = [
    "AnalysisBoundary",
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
    "default_registry",
    "build_language_comparison",
    "merge_comparison_reports",
]
