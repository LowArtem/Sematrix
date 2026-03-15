from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_create_note_api_helper_posts_to_backend_notes_endpoint() -> None:
    api_source = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")

    assert 'export async function createNote(signal?: AbortSignal): Promise<NoteDetail>' in api_source
    assert 'const response = await fetch("/api/notes", {' in api_source
    assert 'method: "POST"' in api_source


def test_plus_card_creates_draft_and_redirects_to_note_editor_route() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    style_source = (FRONTEND_SRC / "styles.css").read_text(encoding="utf-8")

    assert 'const [isCreatingNote, setIsCreatingNote] = useState(false)' in app_source
    assert 'const note = await createNote()' in app_source
    assert 'window.location.assign(`/notes/${note.id}`)' in app_source
    assert 'className="note-card create-note-card"' in app_source
    assert 'Creating draft...' in app_source
    assert '.create-note-card {' in style_source
    assert '.create-note-plus {' in style_source
