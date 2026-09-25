from __future__ import annotations

import sys
from pathlib import Path


AST_ROOT = (Path(__file__).resolve().parents[1] / "AST").resolve()
if not (AST_ROOT / "ast_analyzer.py").is_file():
    raise RuntimeError(f"AST engine not found: {AST_ROOT}")

ast_path = str(AST_ROOT)
if ast_path not in sys.path:
    sys.path.insert(0, ast_path)
