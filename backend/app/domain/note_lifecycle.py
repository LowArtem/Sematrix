from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DraftResetState:
    summary: str = ""
    search_text: str = ""
    embedding: object | None = None
    processing_error: str | None = None
    has_warnings: bool = False
    warnings_count: int = 0
    processing_warnings: list[dict[str, object]] = field(default_factory=list)


def build_draft_reset_state() -> DraftResetState:
    return DraftResetState()


def has_meaningful_content(
    *,
    content_text_flat: str,
    asset_count: int,
    link_count: int,
) -> bool:
    return bool(content_text_flat.strip() or asset_count > 0 or link_count > 0)
