from __future__ import annotations

import re
from collections.abc import Iterable


TAG_NAME_PATTERN = re.compile(r"^[0-9A-Za-zА-Яа-яЁё_]+$")


def normalize_tag_name(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Tag name cannot be empty")
    if any(character.isspace() for character in normalized):
        raise ValueError("Tag name cannot contain spaces")
    if not TAG_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Tag name may contain only Latin/Cyrillic letters, digits, and underscore"
        )
    return normalized


def normalize_tag_names(values: Iterable[str]) -> list[str]:
    normalized_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = normalize_tag_name(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        normalized_values.append(normalized)

    return normalized_values
