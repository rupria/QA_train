"""Language-neutral QA analysis contracts and language adapter registry."""

from importlib import import_module

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

_LAZY_EXPORTS = {
    "default_registry": (".registry", "default_registry"),
    "build_language_comparison": (".comparison", "build_language_comparison"),
    "merge_comparison_reports": (".comparison", "merge_comparison_reports"),
}


def __getattr__(name):
    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY_EXPORTS})

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
