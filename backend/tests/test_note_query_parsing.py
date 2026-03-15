from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTES_DOMAIN_PATH = REPO_ROOT / "backend" / "app" / "domain" / "notes.py"


def test_note_query_parser_reuses_tag_name_rules() -> None:
    source = NOTES_DOMAIN_PATH.read_text(encoding="utf-8")

    assert "from app.domain.tags import TAG_NAME_PATTERN, normalize_tag_names" in source
    assert 'TAG_NAME_INNER_PATTERN = TAG_NAME_PATTERN.pattern.removeprefix("^").removesuffix("$")' in source
    assert 'HASHTAG_PATTERN = re.compile(rf"(?<!\\w)#({TAG_NAME_INNER_PATTERN})(?=$|[^\\w])")' in source


def test_note_query_parser_keeps_tag_only_search_as_empty_text_query() -> None:
    source = NOTES_DOMAIN_PATH.read_text(encoding="utf-8")

    assert 'text_query = HASHTAG_PATTERN.sub(" ", raw_query)' in source
    assert 'normalized_text_query = " ".join(text_query.split())' in source
    assert "return ParsedNoteQuery(text_query=\"\", tag_names=[])" in source
