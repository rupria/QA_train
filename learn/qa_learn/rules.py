from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .html_extract import TextBlock, extract_blocks


RULE_SIGNALS = (
    " should ", " must ", " shall ", " use ", " avoid ", " prefer ", " do not ", " don't ",
    " recommended ", " convention", " guideline", " rule", "규칙", "사용해야", "사용하지",
    "권장", "금지", "피해야", "작성합니다", "지정합니다", "구성합니다", "표기",
)

CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "naming": (
        "name", "naming", "identifier", "camelcase", "pascalcase", "snake_case", "lowercase",
        "uppercase", "underscore", "abbreviation", "acronym", "이름", "명명", "식별자", "표기",
        "카멜", "파스칼", "스네이크", "약어",
    ),
    "declaration": (
        "declare", "declaration", "initialize", "initialization", "scope", "global variable",
        "선언", "초기화", "범위", "전역 변수",
    ),
    "formatting": (
        "indent", "whitespace", "line length", "spacing", "format", "들여쓰기", "공백", "줄 길이", "서식",
    ),
    "code_quality": (
        "readability", "predictability", "cohesion", "coupling", "abstraction", "complexity", "quality",
        "가독성", "예측 가능", "응집", "결합", "추상화", "복잡도", "코드 품질",
    ),
    "api_contract": (
        "endpoint", "http", "request", "response", "header", "parameter", "method", "status code",
        "api", "엔드포인트", "요청", "응답", "헤더", "파라미터", "메서드", "상태 코드",
    ),
    "error_handling": (
        "error", "exception", "failure", "에러", "오류", "예외", "실패",
    ),
    "web_standard": (
        "html", "css", "dom", "web api", "accessibility", "element", "attribute", "웹 표준", "접근성", "요소", "속성",
    ),
}

TARGET_TERMS: dict[str, tuple[str, ...]] = {
    "variable": ("variable", "local variable", "member variable", "변수", "지역 변수", "멤버 변수"),
    "constant": ("constant", "enum", "상수", "열거"),
    "parameter": ("parameter", "argument", "매개변수", "인자"),
    "function": ("function", "method", "함수", "메서드"),
    "class": ("class", "type", "interface", "클래스", "타입", "인터페이스"),
    "property": ("property", "field", "attribute", "프로퍼티", "필드", "속성"),
    "identifier": ("identifier", "name", "naming", "식별자", "이름", "명명"),
    "api": ("api", "endpoint", "request", "response", "엔드포인트", "요청", "응답"),
    "web": ("html", "css", "dom", "element", "attribute", "웹", "요소", "속성"),
}


@dataclass(frozen=True)
class RuleRecord:
    schema_version: int
    rule_id: str
    source_id: str
    source_name: str
    source_type: str
    source_url: str
    source_content_sha256: str
    languages: tuple[str, ...]
    rule_families: tuple[str, ...]
    category: str
    targets: tuple[str, ...]
    heading_path: tuple[str, ...]
    title: str
    statement: str
    examples: tuple[str, ...]
    extraction_method: str
    confidence: float
    review_status: str

    def as_json(self) -> dict[str, object]:
        return asdict(self)


def _contains_term(text: str, term: str) -> bool:
    folded = text.casefold()
    term_folded = term.casefold()
    if re.fullmatch(r"[a-z0-9_ ]+", term_folded):
        return re.search(rf"(?<![a-z0-9_]){re.escape(term_folded)}(?![a-z0-9_])", folded) is not None
    return term_folded in folded


def _matching_labels(text: str, vocabulary: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    return tuple(label for label, terms in vocabulary.items() if any(_contains_term(text, term) for term in terms))


def _is_rule_candidate(text: str, categories: tuple[str, ...], source_type: str) -> bool:
    padded = f" {text.casefold()} "
    has_signal = any(signal in padded for signal in RULE_SIGNALS)
    if has_signal and categories:
        return True
    if source_type in {"api_reference", "cloud_guide"} and "api_contract" in categories:
        return True
    if source_type == "web_standard" and "web_standard" in categories:
        return True
    return False


def _truncate(text: str, limit: int = 1600) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_rules_from_document(html: str, metadata: dict[str, object]) -> list[RuleRecord]:
    blocks = extract_blocks(html)
    source = metadata["source"]
    assert isinstance(source, dict)
    source_id = str(source["id"])
    source_type = str(source["source_type"])
    source_url = str(metadata["url"])
    source_hash = str(metadata["content_sha256"])
    languages = tuple(str(item) for item in source["languages"])
    rule_families = tuple(str(item) for item in source["rule_families"])

    code_by_heading: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for block in blocks:
        if block.kind == "code" and len(block.text) <= 2000:
            code_by_heading[block.heading_path].append(block.text)

    rules: list[RuleRecord] = []
    seen_statements: set[tuple[tuple[str, ...], str]] = set()
    for block in blocks:
        if block.kind != "text" or len(block.text) < 24:
            continue
        categories = _matching_labels(block.text, CATEGORY_TERMS)
        heading_text = " ".join(block.heading_path)
        if not categories:
            categories = _matching_labels(f"{heading_text} {block.text}", CATEGORY_TERMS)
        categories = tuple(category for category in categories if category in rule_families)
        if not _is_rule_candidate(block.text, categories, source_type):
            continue

        targets = _matching_labels(f"{heading_text} {block.text}", TARGET_TERMS)
        if not targets:
            targets = ("general",)
        statement = _truncate(block.text)
        identity = (block.heading_path, statement)
        if identity in seen_statements:
            continue
        seen_statements.add(identity)
        title = block.heading_path[-1] if block.heading_path else source["name"]
        digest_input = json.dumps(
            {"source_id": source_id, "url": source_url, "heading": block.heading_path, "statement": statement},
            ensure_ascii=False,
            sort_keys=True,
        )
        rule_id = f"{source_id}:{hashlib.sha256(digest_input.encode('utf-8')).hexdigest()[:16]}"
        has_signal = any(signal in f" {block.text.casefold()} " for signal in RULE_SIGNALS)
        confidence = 0.9 if has_signal and targets != ("general",) else 0.7 if has_signal else 0.55
        examples = tuple(_truncate(item, 800) for item in code_by_heading.get(block.heading_path, [])[:3])

        for category in categories:
            rules.append(
                RuleRecord(
                    schema_version=1,
                    rule_id=f"{rule_id}:{category}",
                    source_id=source_id,
                    source_name=str(source["name"]),
                    source_type=source_type,
                    source_url=source_url,
                    source_content_sha256=source_hash,
                    languages=languages,
                    rule_families=rule_families,
                    category=category,
                    targets=targets,
                    heading_path=block.heading_path,
                    title=str(title),
                    statement=statement,
                    examples=examples,
                    extraction_method="deterministic-html-rules-v1",
                    confidence=confidence,
                    review_status="pending",
                )
            )
    return rules


def build_rules_from_cache(raw_root: Path) -> list[RuleRecord]:
    rules: list[RuleRecord] = []
    for meta_path in sorted(raw_root.glob("**/*.meta.json")):
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        html_path = meta_path.with_name(str(metadata["html_file"]))
        if not html_path.exists():
            raise FileNotFoundError(f"cached HTML is missing: {html_path}")
        html = html_path.read_text(encoding="utf-8")
        actual_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
        if actual_hash != metadata.get("content_sha256"):
            raise ValueError(f"cached HTML hash mismatch: {html_path}")
        rules.extend(build_rules_from_document(html, metadata))
    rules.sort(key=lambda item: (item.source_id, item.rule_id))
    return rules


def _training_queries(rule: RuleRecord) -> tuple[str, ...]:
    language_text = ", ".join(rule.languages)
    target_text = ", ".join(rule.targets)
    category_text = rule.category.replace("_", " ")
    return (
        f"{language_text}에서 {target_text}의 {category_text} 규칙",
        f"Find the {category_text} convention for {target_text} in {language_text}.",
    )


def write_dataset(
    rules: Iterable[RuleRecord],
    output_root: Path,
    *,
    query_instruction: str = (
        "Given a software convention query in Korean or English, retrieve direct evidence about "
        "identifiers, naming, declarations, code quality, API contracts, and web standards."
    ),
) -> dict[str, object]:
    output_root.mkdir(parents=True, exist_ok=True)
    rule_list = list(rules)
    rules_path = output_root / "rules.jsonl"
    examples_path = output_root / "training_examples.jsonl"
    swift_path = output_root / "swift_embedding_candidates.jsonl"
    manifest_path = output_root / "manifest.json"

    with rules_path.open("w", encoding="utf-8", newline="\n") as handle:
        for rule in rule_list:
            handle.write(json.dumps(rule.as_json(), ensure_ascii=False, sort_keys=True) + "\n")

    example_count = 0
    swift_count = 0
    with examples_path.open("w", encoding="utf-8", newline="\n") as handle, swift_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as swift_handle:
        for rule in rule_list:
            positive = f"{rule.title}\n{rule.statement}"
            for language, query in zip(("ko", "en"), _training_queries(rule), strict=True):
                example = {
                    "schema_version": 1,
                    "task": "rule_retrieval",
                    "query_language": language,
                    "query": query,
                    "positive": positive,
                    "positive_rule_id": rule.rule_id,
                    "category": rule.category,
                    "targets": list(rule.targets),
                    "source_id": rule.source_id,
                    "source_url": rule.source_url,
                    "split_group": rule.source_content_sha256,
                    "review_status": rule.review_status,
                    "training_eligible": rule.review_status == "accepted",
                }
                handle.write(json.dumps(example, ensure_ascii=False, sort_keys=True) + "\n")
                example_count += 1
                swift_example = {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Instruct: {query_instruction}\nQuery: {query}",
                        }
                    ],
                    "positive_messages": [[{"role": "user", "content": positive}]],
                    "metadata": {
                        "query_language": language,
                        "positive_rule_id": rule.rule_id,
                        "source_id": rule.source_id,
                        "split_group": rule.source_content_sha256,
                        "review_status": rule.review_status,
                        "training_eligible": rule.review_status == "accepted",
                    },
                }
                swift_handle.write(json.dumps(swift_example, ensure_ascii=False, sort_keys=True) + "\n")
                swift_count += 1

    category_counts = Counter(rule.category for rule in rule_list)
    source_counts = Counter(rule.source_id for rule in rule_list)
    manifest = {
        "schema_version": 1,
        "rule_count": len(rule_list),
        "training_example_count": example_count,
        "swift_candidate_count": swift_count,
        "categories": dict(sorted(category_counts.items())),
        "sources": dict(sorted(source_counts.items())),
        "outputs": {
            "rules": rules_path.name,
            "training_examples": examples_path.name,
            "swift_embedding_candidates": swift_path.name,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
