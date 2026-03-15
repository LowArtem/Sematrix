import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re
from typing import cast


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTES_DOMAIN_PATH = REPO_ROOT / "backend" / "app" / "domain" / "notes.py"


def _load_query_parser_namespace() -> dict[str, object]:
    source = NOTES_DOMAIN_PATH.read_text(encoding="utf-8")
    module = ast.parse(source)
    target_nodes: list[ast.stmt] = []

    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and target.id in {"TAG_NAME_INNER_PATTERN", "HASHTAG_PATTERN", "TEXT_QUERY_CONTENT_PATTERN"}
            for target in node.targets
        ):
            target_nodes.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "ParsedNoteQuery":
            target_nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "parse_note_query":
            target_nodes.append(node)

    extracted_module = ast.Module(body=target_nodes, type_ignores=[])
    ast.fix_missing_locations(extracted_module)

    tag_name_pattern = re.compile(r"^[0-9A-Za-zА-Яа-яЁё_]+$")

    def normalize_tag_names(values: list[str]) -> list[str]:
        normalized_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip().lower()
            if not normalized or not tag_name_pattern.fullmatch(normalized):
                raise ValueError("Invalid tag name")
            if normalized in seen:
                continue
            seen.add(normalized)
            normalized_values.append(normalized)
        return normalized_values

    namespace: dict[str, object] = {
        "__builtins__": __builtins__,
        "dataclass": dataclass,
        "re": re,
        "TAG_NAME_PATTERN": tag_name_pattern,
        "normalize_tag_names": normalize_tag_names,
    }
    exec(compile(extracted_module, str(NOTES_DOMAIN_PATH), "exec"), namespace)
    return namespace


def test_note_query_parser_reuses_tag_name_rules() -> None:
    source = NOTES_DOMAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domain.tags import TAG_NAME_PATTERN, normalize_tag_names" in source
    assert 'TAG_NAME_INNER_PATTERN = TAG_NAME_PATTERN.pattern.removeprefix("^").removesuffix("$")' in source
    assert 'HASHTAG_PATTERN = re.compile(rf"(?<!\\w)#({TAG_NAME_INNER_PATTERN})(?=$|[\\s.,!?;:)\\]])")' in source
    assert 'TEXT_QUERY_CONTENT_PATTERN = re.compile(r"[0-9A-Za-zА-Яа-яЁё]")' in source


def test_note_query_parser_keeps_tag_only_search_as_empty_text_query() -> None:
    source = NOTES_DOMAIN_PATH.read_text(encoding="utf-8")

    assert 'text_query = HASHTAG_PATTERN.sub(" ", raw_query)' in source
    assert 'normalized_text_query = " ".join(text_query.split())' in source
    assert 'if normalized_text_query and not TEXT_QUERY_CONTENT_PATTERN.search(normalized_text_query):' in source
    assert "return ParsedNoteQuery(text_query=\"\", tag_names=[])" in source


def test_note_query_parser_extracts_normalized_unique_tags_and_remaining_text() -> None:
    namespace = _load_query_parser_namespace()
    parse_note_query = cast(Callable[[str], object], namespace["parse_note_query"])

    parsed_query = parse_note_query("  deep work #Focus sync with #план and #focus tomorrow  ")

    assert getattr(parsed_query, "text_query") == "deep work sync with and tomorrow"
    assert getattr(parsed_query, "tag_names") == ["focus", "план"]


def test_note_query_parser_ignores_invalid_or_embedded_hashtags() -> None:
    namespace = _load_query_parser_namespace()
    parse_note_query = cast(Callable[[str], object], namespace["parse_note_query"])

    parsed_query = parse_note_query("email#focus keep #bad-tag #good_tag #две-части #ok")

    assert getattr(parsed_query, "text_query") == "email#focus keep #bad-tag #две-части"
    assert getattr(parsed_query, "tag_names") == ["good_tag", "ok"]


def test_note_query_parser_accepts_trailing_punctuation_after_valid_tag() -> None:
    namespace = _load_query_parser_namespace()
    parse_note_query = cast(Callable[[str], object], namespace["parse_note_query"])

    parsed_query = parse_note_query("review #Focus, then ship #ready!")

    assert getattr(parsed_query, "text_query") == "review , then ship !"
    assert getattr(parsed_query, "tag_names") == ["focus", "ready"]


def test_note_query_parser_treats_punctuation_only_remainder_as_tag_only_search() -> None:
    namespace = _load_query_parser_namespace()
    parse_note_query = cast(Callable[[str], object], namespace["parse_note_query"])

    parsed_query = parse_note_query(" #Focus, #ready! ")

    assert getattr(parsed_query, "text_query") == ""
    assert getattr(parsed_query, "tag_names") == ["focus", "ready"]
