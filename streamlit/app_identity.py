"""Shared product identity for Streamlit Cloud and the local app."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "app_manifest.json"


def _load_manifest() -> dict:
    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or not isinstance(payload.get("product_name"), str)
        or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", str(payload.get("app_version")))
    ):
        raise RuntimeError("app_manifest.json의 제품명 또는 버전 형식이 올바르지 않습니다.")
    return payload


APP_MANIFEST = _load_manifest()
PRODUCT_NAME = APP_MANIFEST["product_name"]
APP_VERSION = APP_MANIFEST["app_version"]


def distribution_name() -> str:
    explicit = os.environ.get("QA_APP_MODE", "").strip().lower()
    if explicit == "cloud":
        return "Streamlit Cloud"
    if explicit == "local":
        return "로컬 앱"
    return "로컬 앱" if os.environ.get("QA_WEB_ALLOW_LOCAL", "1") == "1" else "Streamlit Cloud"


def version_label() -> str:
    return f"v{APP_VERSION} · {distribution_name()}"
