from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class SourcePage:
    url: str
    languages: tuple[str, ...]


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    name: str
    source_type: str
    languages: tuple[str, ...]
    rule_families: tuple[str, ...]
    allowed_domains: tuple[str, ...]
    pages: tuple[SourcePage, ...]

    @property
    def urls(self) -> tuple[str, ...]:
        return tuple(page.url for page in self.pages)


def _require_string_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field_name} must be a non-empty string list")
    return tuple(value)


def load_catalog(path: Path) -> list[SourceDefinition]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported source catalog schema_version")
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("source catalog must contain sources")

    definitions: list[SourceDefinition] = []
    seen_ids: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise ValueError("each source must be an object")
        source_id = raw.get("id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source id must be a non-empty string")
        if source_id in seen_ids:
            raise ValueError(f"duplicate source id: {source_id}")
        seen_ids.add(source_id)

        allowed_domains = _require_string_list(raw.get("allowed_domains"), "allowed_domains")
        raw_pages = raw.get("urls")
        if not isinstance(raw_pages, list) or not raw_pages:
            raise ValueError("urls must be a non-empty list")
        source_languages = _require_string_list(raw.get("languages"), "languages")
        pages: list[SourcePage] = []
        for raw_page in raw_pages:
            if isinstance(raw_page, str):
                url = raw_page
                page_languages = source_languages
            elif isinstance(raw_page, dict):
                url = raw_page.get("url")
                if not isinstance(url, str) or not url:
                    raise ValueError("page url must be a non-empty string")
                page_languages = _require_string_list(raw_page.get("languages"), "page languages")
            else:
                raise ValueError("each url entry must be a string or page object")
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in allowed_domains:
                raise ValueError(f"URL is outside the source allowlist: {url}")
            pages.append(SourcePage(url=url, languages=page_languages))

        definitions.append(
            SourceDefinition(
                source_id=source_id,
                name=str(raw.get("name") or source_id),
                source_type=str(raw.get("source_type") or "reference"),
                languages=source_languages,
                rule_families=_require_string_list(raw.get("rule_families"), "rule_families"),
                allowed_domains=allowed_domains,
                pages=tuple(pages),
            )
        )
    return definitions
