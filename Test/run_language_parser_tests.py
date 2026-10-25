"""Run QA Train parser and comparison smoke tests by language or family."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AST_ROOT = ROOT / "AST"
sys.path.insert(0, str(AST_ROOT))

from language_cases import CASES, CASES_BY_ID, GROUPS, LanguageCase  # noqa: E402
from qa_ast import EdgeKind, NodeKind, build_language_comparison, default_registry  # noqa: E402
from qa_ast.languages.python.comparison import build_comparison  # noqa: E402


@dataclass
class TestResult:
    language: str
    group: str
    check: str
    passed: bool
    elapsed_ms: int
    nodes: int = 0
    calls: int = 0
    changes: int = 0
    parser: str = ""
    error: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic parser tests without executing the fixture source.",
    )
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--language", action="append", choices=sorted(CASES_BY_ID),
                           help="Language id to test. Repeat to select multiple languages.")
    selectors.add_argument("--group", choices=GROUPS, help="Language family to test.")
    selectors.add_argument("--all", action="store_true", help="Test every supported language.")
    selectors.add_argument("--list", action="store_true", help="List testable languages and exit.")
    parser.add_argument("--check", choices=("parse", "compare", "all"), default="all",
                        help="Validation stage. Default: all.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args()


def selected_cases(args: argparse.Namespace) -> list[LanguageCase]:
    if args.language:
        return [CASES_BY_ID[item] for item in args.language]
    if args.group:
        return [case for case in CASES if case.group == args.group]
    if args.all:
        return list(CASES)
    raise ValueError("select --language, --group, --all, or --list")


def write_versions(root: Path, case: LanguageCase) -> tuple[Path, Path]:
    base = root / "Ver.A"
    target = root / "Ver.B"
    base.mkdir()
    target.mkdir()
    (base / case.filename).write_text(case.source(1), encoding="utf-8")
    (target / case.filename).write_text(case.source(2), encoding="utf-8")
    return base, target


def verify_parse(case: LanguageCase, target: Path) -> tuple[int, int, str]:
    adapter = default_registry().get(case.language_id)
    source = target / case.filename
    if not adapter.supports_file(source):
        raise AssertionError(f"adapter does not accept {case.filename}")
    graph = adapter.analyze(target)
    graph.validate()
    if graph.languages != [case.language_id]:
        raise AssertionError(f"unexpected graph languages: {graph.languages}")
    fatal = [boundary for boundary in graph.boundaries
             if boundary.kind in {"parser_unavailable", "parse_error", "parse_diagnostic"}]
    if fatal:
        details = "; ".join(f"{item.kind}: {item.message}" for item in fatal[:3])
        raise AssertionError(details)
    modules = [node for node in graph.nodes if node.kind is NodeKind.MODULE]
    if not modules:
        raise AssertionError("no module node emitted")
    if case.language_id != "python" and graph.metadata.get("parsed_files") != 1:
        raise AssertionError(f"parsed_files={graph.metadata.get('parsed_files')!r}, expected 1")
    calls = sum(edge.kind is EdgeKind.CALLS for edge in graph.edges)
    return len(graph.nodes), calls, str(graph.metadata.get("parser", ""))


def verify_compare(case: LanguageCase, base: Path, target: Path) -> int:
    if case.language_id == "python":
        report = build_comparison(base, target, max_depth=3)
    else:
        report = build_language_comparison(base, target, [case.language_id], max_depth=3)
    if report["status"] != "analyzed":
        raise AssertionError(f"comparison status={report['status']}: {report.get('errors', [])[:2]}")
    count = int(report["summary"]["total_changes"])
    if count < 1:
        raise AssertionError("Ver.A/Ver.B literal change was not detected")
    return count


def run_case(case: LanguageCase, check: str) -> TestResult:
    started = time.perf_counter()
    result = TestResult(case.language_id, case.group, check, passed=False, elapsed_ms=0)
    try:
        with tempfile.TemporaryDirectory(prefix=f"qa-train-{case.language_id}-") as temporary:
            base, target = write_versions(Path(temporary), case)
            if check in {"parse", "all"}:
                result.nodes, result.calls, result.parser = verify_parse(case, target)
            if check in {"compare", "all"}:
                result.changes = verify_compare(case, base, target)
        result.passed = True
    except Exception as exc:  # Keep the suite running so every failing language is reported.
        result.error = f"{exc.__class__.__name__}: {exc}"
    result.elapsed_ms = round((time.perf_counter() - started) * 1000)
    return result


def print_list() -> None:
    for group in GROUPS:
        languages = ", ".join(case.language_id for case in CASES if case.group == group)
        print(f"{group}: {languages}")


def print_results(results: list[TestResult], as_json: bool) -> None:
    if as_json:
        print(json.dumps({
            "summary": {
                "total": len(results),
                "passed": sum(item.passed for item in results),
                "failed": sum(not item.passed for item in results),
            },
            "results": [asdict(item) for item in results],
        }, ensure_ascii=False, indent=2))
        return
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        details = (f"nodes={item.nodes} calls={item.calls} changes={item.changes} "
                   f"time={item.elapsed_ms}ms")
        print(f"[{status}] {item.language:<14} {details}")
        if item.error:
            print(f"       {item.error}")
    passed = sum(item.passed for item in results)
    print(f"\nResult: {passed}/{len(results)} passed")


def main() -> int:
    args = parse_args()
    if args.list:
        print_list()
        return 0
    try:
        cases = selected_cases(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    results = [run_case(case, args.check) for case in cases]
    print_results(results, args.json)
    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
