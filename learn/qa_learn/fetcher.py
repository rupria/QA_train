from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .catalog import SourceDefinition


USER_AGENT = "QA-Train-Learn/0.1 (+https://github.com/rupria/QA_train)"
DEFAULT_MAX_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class FetchResult:
    source_id: str
    url: str
    status: str
    html_path: str | None
    content_sha256: str | None
    error: str | None = None


def _safe_slug(url: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.hostname}{parsed.path}".strip("/") or parsed.hostname or "source"
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw).strip("-.")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"{slug[:100]}-{digest}"


def fetch_source(
    source: SourceDefinition,
    output_root: Path,
    *,
    force: bool = False,
    timeout_seconds: int = 30,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> list[FetchResult]:
    source_dir = output_root / source.source_id
    source_dir.mkdir(parents=True, exist_ok=True)
    results: list[FetchResult] = []

    for page in source.pages:
        url = page.url
        slug = _safe_slug(url)
        html_path = source_dir / f"{slug}.html"
        meta_path = source_dir / f"{slug}.meta.json"
        if html_path.exists() and meta_path.exists() and not force:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            results.append(
                FetchResult(
                    source_id=source.source_id,
                    url=url,
                    status="cached",
                    html_path=str(html_path),
                    content_sha256=metadata.get("content_sha256"),
                )
            )
            continue

        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise ValueError(f"unsupported content type: {content_type}")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError(f"document exceeds {max_bytes} bytes")
                charset = response.headers.get_content_charset() or "utf-8"
                html = body.decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            results.append(
                FetchResult(
                    source_id=source.source_id,
                    url=url,
                    status="error",
                    html_path=None,
                    content_sha256=None,
                    error=str(exc),
                )
            )
            continue

        content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        html_path.write_text(html, encoding="utf-8")
        metadata = {
            "schema_version": 1,
            "source": {
                "id": source.source_id,
                "name": source.name,
                "source_type": source.source_type,
                "languages": list(page.languages),
                "rule_families": list(source.rule_families),
            },
            "url": url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "content_sha256": content_hash,
            "html_file": html_path.name,
        }
        meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(
            FetchResult(
                source_id=source.source_id,
                url=url,
                status="fetched",
                html_path=str(html_path),
                content_sha256=content_hash,
            )
        )
    return results


def result_as_dict(result: FetchResult) -> dict[str, object]:
    return asdict(result)
