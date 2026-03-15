from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_note_list_api_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "routes" / "notes.py",
        BACKEND_APP / "domain" / "notes.py",
        BACKEND_APP / "infra" / "notes.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_note_list_route_uses_paginated_contract() -> None:
    route_source = (BACKEND_APP / "api" / "routes" / "notes.py").read_text(encoding="utf-8")

    assert '@api_notes_router.get("", response_model=PaginatedResponse[NoteCardDto])' in route_source
    assert "q: str | None = Query(default=None)" in route_source
    assert "folder_id: UUID | None = Query(default=None)" in route_source
    assert "limit: int = Query(default=50, ge=0)" in route_source
    assert "offset: int = Query(default=0, ge=0)" in route_source
    assert "return _to_note_list_dto(service.list_notes(q=q, folder_id=folder_id, limit=limit, offset=offset))" in route_source


def test_note_list_service_parses_hashtags_before_repository_lookup() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")

    assert "class ParsedNoteQuery:" in domain_source
    assert "raw_tag_names = HASHTAG_PATTERN.findall(raw_query)" in domain_source
    assert "normalized_tag_names = normalize_tag_names(raw_tag_names) if raw_tag_names else []" in domain_source
    assert 'normalized_text_query = " ".join(text_query.split())' in domain_source
    assert "parsed_query = parse_note_query(q)" in domain_source


def test_note_list_service_keeps_tag_only_queries_on_listing_path() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")

    assert "if parsed_query.text_query:" in domain_source
    assert "return self._list_hybrid_notes(" in domain_source
    assert "result = self._note_repository.list_notes(" in domain_source
    assert "tag_names=parsed_query.tag_names," in domain_source
    assert "text_query=parsed_query.text_query," in domain_source


def test_note_list_repository_applies_and_tag_filter_and_stable_sort() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert ".where(Tag.name.in_(tag_names))" in infra_source
    assert ".having(func.count(func.distinct(Tag.name)) == len(tag_names))" in infra_source
    assert ".order_by(Note.updated_at.desc(), Note.id.desc())" in infra_source
    assert ".options(selectinload(Note.tags))" in infra_source
