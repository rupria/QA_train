from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser


WHITESPACE_RE = re.compile(r"\s+")
HEADING_TAGS = {f"h{level}" for level in range(1, 7)}
CONTENT_TAGS = {"p", "li", "dt", "dd", "pre", "td", "th", "blockquote"}
SKIP_TAGS = {"script", "style", "svg", "noscript", "template"}


@dataclass(frozen=True)
class TextBlock:
    kind: str
    text: str
    heading_path: tuple[str, ...]


class HTMLBlockExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[TextBlock] = []
        self._heading_path: list[str] = []
        self._capture_tag: str | None = None
        self._capture_depth = 0
        self._buffer: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if self._capture_tag is not None:
            self._capture_depth += 1
            if tag in {"br", "hr"}:
                self._buffer.append("\n")
            return
        if tag in HEADING_TAGS or tag in CONTENT_TAGS:
            self._capture_tag = tag
            self._capture_depth = 1
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth or self._capture_tag is None:
            return
        self._capture_depth -= 1
        if self._capture_depth > 0:
            return

        text = WHITESPACE_RE.sub(" ", "".join(self._buffer)).strip()
        captured_tag = self._capture_tag
        self._capture_tag = None
        self._buffer = []
        self._capture_depth = 0
        if not text:
            return

        if captured_tag in HEADING_TAGS:
            level = int(captured_tag[1])
            self._heading_path = self._heading_path[: level - 1]
            while len(self._heading_path) < level - 1:
                self._heading_path.append("")
            self._heading_path.append(text)
            self.blocks.append(TextBlock(kind="heading", text=text, heading_path=tuple(self._heading_path)))
            return

        kind = "code" if captured_tag == "pre" else "text"
        self.blocks.append(TextBlock(kind=kind, text=text, heading_path=tuple(item for item in self._heading_path if item)))

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and self._capture_tag is not None:
            self._buffer.append(data)


def extract_blocks(html: str) -> list[TextBlock]:
    parser = HTMLBlockExtractor()
    parser.feed(html)
    parser.close()
    return parser.blocks
