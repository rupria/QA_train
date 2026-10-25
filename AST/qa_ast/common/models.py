"""Serializable graph contracts shared by every language adapter.

Parser objects such as ``ast.AST`` or Tree-sitter nodes must never cross this
boundary.  Adapters retain those objects internally and emit only these stable
facts plus optional JSON-compatible ``language_data``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any


class NodeKind(str, Enum):
    PROJECT = "project"
    FILE = "file"
    MODULE = "module"
    NAMESPACE = "namespace"
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    FUNCTION = "function"
    METHOD = "method"
    CONSTRUCTOR = "constructor"
    PROPERTY = "property"
    FIELD = "field"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    UI_PAGE = "ui_page"
    UI_COMPONENT = "ui_component"
    CONTENT = "content"
    EVENT = "event"
    API = "api"
    DATABASE = "database"
    TABLE = "table"
    COLUMN = "column"
    CONFIGURATION = "configuration"
    PERMISSION = "permission"
    EXTERNAL_SERVICE = "external_service"
    FEATURE = "feature"


class EdgeKind(str, Enum):
    CONTAINS = "contains"
    DECLARES = "declares"
    IMPORTS = "imports"
    CALLS = "calls"
    REFERENCES = "references"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    OVERRIDES = "overrides"
    READS = "reads"
    WRITES = "writes"
    RETURNS = "returns"
    PASSES_TO = "passes_to"
    TRIGGERS = "triggers"
    RENDERS = "renders"
    NAVIGATES = "navigates"
    REQUESTS = "requests"
    HANDLED_BY = "handled_by"
    VALIDATES = "validates"
    DEPENDS_ON = "depends_on"
    MIGRATES = "migrates"
    AFFECTS = "affects"


class Resolution(str, Enum):
    EXACT = "exact"
    STATIC = "static"
    INFERRED = "inferred"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class SourceRange:
    start_line: int
    end_line: int
    start_column: int | None = None
    end_column: int | None = None

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("source range lines must be positive and ordered")


@dataclass(frozen=True)
class Evidence:
    file: str
    parser: str
    source_range: SourceRange | None = None
    expression: str | None = None
    rule: str | None = None
    version: str | None = None


@dataclass
class CommonNode:
    id: str
    kind: NodeKind
    name: str
    language: str
    qualified_name: str | None = None
    file: str | None = None
    source_range: SourceRange | None = None
    signature: str | None = None
    visibility: str | None = None
    language_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.name or not self.language:
            raise ValueError("node id, name and language are required")


@dataclass
class CommonEdge:
    id: str
    kind: EdgeKind
    source: str
    target: str
    resolution: Resolution
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("edge confidence must be between 0 and 1")


@dataclass(frozen=True)
class AnalysisBoundary:
    kind: str
    message: str
    file: str | None = None
    source_range: SourceRange | None = None
    language: str | None = None


@dataclass
class Change:
    id: str
    node_id: str
    change_type: str
    changed_fields: list[str] = field(default_factory=list)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class ImpactResult:
    change_id: str
    affected_node_id: str
    impact_type: str
    impact_level: str
    confidence: float
    distance: int
    path: list[str] = field(default_factory=list)
    boundaries: list[AnalysisBoundary] = field(default_factory=list)


@dataclass
class ProjectGraph:
    root: str
    languages: list[str]
    nodes: list[CommonNode]
    edges: list[CommonEdge]
    boundaries: list[AnalysisBoundary] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("project graph contains duplicate node ids")
        known = set(node_ids)
        dangling = [edge.id for edge in self.edges if edge.source not in known or edge.target not in known]
        if dangling:
            raise ValueError(f"project graph contains dangling edges: {', '.join(dangling[:5])}")

    def to_dict(self) -> dict[str, Any]:
        return _json_value(self)


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _json_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
