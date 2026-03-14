from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from app.domain.errors import DomainError


URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
TEXT_FILE_EXTENSIONS = {
    ".csv",
    ".json",
    ".log",
    ".md",
    ".rst",
    ".text",
    ".toml",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
WEB_PAGE_EXTENSIONS = {"", ".asp", ".aspx", ".cfm", ".cgi", ".htm", ".html", ".jsp", ".php"}
OTHER_FILE_EXTENSIONS = {
    ".7z",
    ".avif",
    ".bmp",
    ".doc",
    ".docx",
    ".epub",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".odt",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".rtf",
    ".svg",
    ".tar",
    ".wav",
    ".webm",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}


@dataclass(frozen=True)
class ExtractedLink:
    url: str
    normalized_url: str
    link_type: str


@dataclass(frozen=True)
class ParsedNoteContent:
    content_text_flat: str
    asset_ids: list[UUID]
    links: list[ExtractedLink]


def parse_note_content(content_json: dict[str, Any]) -> ParsedNoteContent:
    if content_json.get("type") != "doc":
        raise DomainError("content_json must be a Tiptap doc node")

    text_parts: list[str] = []
    asset_ids: list[UUID] = []
    links: list[ExtractedLink] = []
    seen_asset_ids: set[UUID] = set()
    seen_links: set[str] = set()

    def add_link(raw_url: str) -> None:
        normalized_url = normalize_note_url(raw_url)
        if normalized_url is None or normalized_url in seen_links:
            return
        seen_links.add(normalized_url)
        links.append(
            ExtractedLink(
                url=clean_note_url(raw_url),
                normalized_url=normalized_url,
                link_type=classify_note_link(normalized_url),
            )
        )

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return

        if not isinstance(node, dict):
            return

        node_type = node.get("type")
        attrs_value = node.get("attrs")
        attrs: dict[str, Any] = attrs_value if isinstance(attrs_value, dict) else {}

        if node_type == "text" and isinstance(node.get("text"), str):
            text_value = node["text"]
            text_parts.append(text_value)
            for match in URL_PATTERN.findall(text_value):
                add_link(match)

        if node_type == "image" and isinstance(attrs.get("assetId"), str):
            try:
                asset_id = UUID(attrs["assetId"])
            except ValueError as exc:
                raise DomainError("content_json contains an invalid image assetId") from exc
            if asset_id not in seen_asset_ids:
                seen_asset_ids.add(asset_id)
                asset_ids.append(asset_id)

        marks = node.get("marks")
        if isinstance(marks, list):
            for mark in marks:
                if not isinstance(mark, dict) or mark.get("type") != "link":
                    continue
                mark_attrs_value = mark.get("attrs")
                mark_attrs: dict[str, Any] = (
                    mark_attrs_value if isinstance(mark_attrs_value, dict) else {}
                )
                href = mark_attrs.get("href")
                if isinstance(href, str):
                    add_link(href)

        walk(node.get("content"))

    walk(content_json)

    content_text_flat = " ".join(part.strip() for part in text_parts if part.strip())

    return ParsedNoteContent(
        content_text_flat=content_text_flat,
        asset_ids=asset_ids,
        links=links,
    )


def clean_note_url(raw_url: str) -> str:
    return raw_url.strip().rstrip(".,!?;:)]")


def normalize_note_url(raw_url: str) -> str | None:
    candidate = clean_note_url(raw_url)
    parsed = urlparse(candidate)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return None

    port = parsed.port
    if port is None or (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        netloc = hostname
    else:
        netloc = f"{hostname}:{port}"

    normalized_query = urlencode(
        sorted(parse_qsl(parsed.query, keep_blank_values=True)),
        doseq=True,
    )
    return urlunparse((scheme, netloc, parsed.path or "", "", normalized_query, ""))


def classify_note_link(normalized_url: str) -> str:
    parsed = urlparse(normalized_url)
    hostname = (parsed.hostname or "").lower()
    path = parsed.path or ""
    path_lower = path.lower()
    path_segments = [segment for segment in path_lower.split("/") if segment]
    extension = ""
    if path_segments and "." in path_segments[-1]:
        extension = f".{path_segments[-1].rsplit('.', 1)[-1]}"

    if hostname in {"youtu.be", "www.youtu.be"}:
        return "youtube_video"

    if hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if path_lower in {"/watch", "/live"} and parsed.query:
            return "youtube_video"
        if path_lower.startswith(("/shorts/", "/embed/", "/live/")):
            return "youtube_video"
        if path_lower.startswith(("/channel/", "/@", "/c/", "/user/")):
            return "youtube_channel"

    if extension in TEXT_FILE_EXTENSIONS:
        return "text_file"

    if extension in OTHER_FILE_EXTENSIONS:
        return "other"

    if extension in WEB_PAGE_EXTENSIONS:
        return "web"

    if extension:
        return "other"

    return "web"
