"""Feature declarations used to expose honest per-language support."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AnalysisCapabilities:
    parse: bool = False
    symbols: bool = False
    imports: bool = False
    calls: bool = False
    references: bool = False
    inheritance: bool = False
    value_flow: bool = False
    ui_mapping: bool = False
    api_mapping: bool = False
    db_mapping: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)
