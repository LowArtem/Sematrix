from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re

import trafilatura
from readability import Document


_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")


class HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(chunk.strip() for chunk in self._chunks if chunk.strip())


def extract_main_text(*, html: str) -> str:
    extracted_text = _extract_with_trafilatura(html=html)
    if extracted_text:
        return extracted_text

    return _extract_with_readability(html=html)


def _extract_with_trafilatura(*, html: str) -> str:
    extracted_text = trafilatura.extract(
        html,
        output_format="txt",
        include_comments=False,
        include_links=False,
        include_tables=True,
        favor_precision=True,
        deduplicate=True,
    )
    if not isinstance(extracted_text, str):
        return ""
    return _normalize_extracted_text(extracted_text)


def _extract_with_readability(*, html: str) -> str:
    try:
        summary_html = Document(html).summary(html_partial=True)
    except Exception:
        return ""

    parser = HtmlTextExtractor()
    parser.feed(summary_html)
    parser.close()
    return _normalize_extracted_text(parser.get_text())


def _normalize_extracted_text(text: str) -> str:
    normalized_text = unescape(text).replace("\r\n", "\n").replace("\r", "\n")
    normalized_lines = [line.strip() for line in normalized_text.split("\n")]
    collapsed_text = "\n".join(line for line in normalized_lines if line)
    collapsed_text = _MULTI_BLANK_LINE_RE.sub("\n\n", collapsed_text)
    return collapsed_text.strip()
