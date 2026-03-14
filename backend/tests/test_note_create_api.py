from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_note_create_api_files_exist() -> None:
    expected_paths = [
        BACKEND_APP / "api" / "routes" / "notes.py",
        BACKEND_APP / "domain" / "notes.py",
        BACKEND_APP / "infra" / "notes.py",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_note_create_route_is_registered() -> None:
    router_source = (BACKEND_APP / "api" / "router.py").read_text(encoding="utf-8")
    route_source = (BACKEND_APP / "api" / "routes" / "notes.py").read_text(encoding="utf-8")
    dependency_source = (BACKEND_APP / "api" / "dependencies.py").read_text(encoding="utf-8")
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert "from app.api.routes.notes import api_notes_router" in router_source
    assert "api_router.include_router(api_notes_router)" in router_source
    assert 'api_notes_router = APIRouter(prefix="/notes", tags=["notes"])' in route_source
    assert '@api_notes_router.post("", response_model=NoteDetailDto, status_code=status.HTTP_201_CREATED)' in route_source
    assert '@api_notes_router.get("/{note_id}", response_model=NoteDetailDto)' in route_source
    assert "def get_note_service(session: Session = Depends(get_db_session)) -> NoteService:" in dependency_source
    assert "class NoteService:" in domain_source
    assert "class SqlAlchemyNoteRepository:" in infra_source


def test_note_create_uses_minimal_empty_draft_defaults() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")
    route_source = (BACKEND_APP / "api" / "routes" / "notes.py").read_text(encoding="utf-8")

    assert 'EMPTY_DOCUMENT = {"type": "doc", "content": []}' in infra_source
    assert "note = Note(content_json=EMPTY_DOCUMENT)" in infra_source
    assert 'status=note.status' in route_source
    assert 'index_version=note.index_version' in route_source


def test_note_detail_route_uses_service_not_found_handling() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert "def get_note(self, note_id: UUID) -> NoteResult:" in domain_source
    assert 'raise NotFoundError("Note not found")' in domain_source
    assert "def get_note(self, note_id: UUID) -> NoteRecord | None:" in infra_source
    assert "note = self._get_note_with_relations(note_id)" in infra_source
