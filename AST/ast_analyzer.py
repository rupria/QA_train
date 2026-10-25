"""Compatibility CLI for the Python language adapter implementation."""

from qa_ast.languages.python.analyzer import *  # noqa: F401,F403
from qa_ast.languages.python.analyzer import main


if __name__ == "__main__":
    raise SystemExit(main())
