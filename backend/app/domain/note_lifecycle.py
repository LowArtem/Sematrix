from __future__ import annotations


def has_meaningful_content(
    *,
    content_text_flat: str,
    asset_count: int,
    link_count: int,
) -> bool:
    return bool(content_text_flat.strip() or asset_count > 0 or link_count > 0)
