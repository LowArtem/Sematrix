from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_tag_list_api_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "routes" / "tags.py",
        BACKEND_APP / "domain" / "tags.py",
        BACKEND_APP / "infra" / "tags.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_tag_list_route_uses_paginated_contract() -> None:
    route_source = (BACKEND_APP / "api" / "routes" / "tags.py").read_text(encoding="utf-8")

    assert '@api_tags_router.get("", response_model=PaginatedResponse[TagDto])' in route_source
    assert "q: str | None = Query(default=None)" in route_source
    assert "limit: int = Query(default=50, ge=0)" in route_source
    assert "offset: int = Query(default=0, ge=0)" in route_source
    assert "return _to_tag_list_dto(service.list_tags(q=q, limit=limit, offset=offset))" in route_source


def test_tag_list_dependency_and_router_registration_exist() -> None:
    dependencies_source = (BACKEND_APP / "api" / "dependencies.py").read_text(encoding="utf-8")
    router_source = (BACKEND_APP / "api" / "router.py").read_text(encoding="utf-8")

    assert "from app.domain.tags import TagService" in dependencies_source
    assert "from app.infra.tags import SqlAlchemyTagRepository" in dependencies_source
    assert "def get_tag_service(session: Session = Depends(get_db_session)) -> TagService:" in dependencies_source
    assert "return TagService(tag_repository=SqlAlchemyTagRepository(session=session))" in dependencies_source
    assert "from app.api.routes.tags import api_tags_router" in router_source
    assert "api_router.include_router(api_tags_router)" in router_source


def test_tag_list_repository_prioritizes_matches_then_counts_then_name() -> None:
    infra_source = (BACKEND_APP / "infra" / "tags.py").read_text(encoding="utf-8")

    assert ".outerjoin(NoteTag, NoteTag.tag_id == Tag.id)" in infra_source
    assert "case((Tag.name.ilike(f\"%{normalized_query}%\"), 0), else_=1).asc()" in infra_source
    assert "statement = statement.order_by(note_count.desc(), Tag.name.asc(), Tag.id.asc())" in infra_source
    assert "statement = statement.order_by(" in infra_source
    assert "total = self._session.scalar(select(func.count()).select_from(statement.subquery())) or 0" in infra_source


def test_tag_service_maps_normalized_name_from_backend_tag_value() -> None:
    domain_source = (BACKEND_APP / "domain" / "tags.py").read_text(encoding="utf-8")

    assert "class TagService:" in domain_source
    assert "normalized_name=tag.name" in domain_source
    assert "result = self._tag_repository.list_tags(q=q, limit=limit, offset=offset)" in domain_source
