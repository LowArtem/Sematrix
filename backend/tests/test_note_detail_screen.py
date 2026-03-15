from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_note_detail_screen_files_exist() -> None:
    expected_paths = [
        FRONTEND_SRC / "App.tsx",
        FRONTEND_SRC / "api.ts",
        FRONTEND_SRC / "styles.css",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_note_detail_screen_loads_note_and_folder_data_from_public_api() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    api_source = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")

    assert "export function getNoteDetail(noteId: string, signal?: AbortSignal): Promise<NoteDetail>" in api_source
    assert 'return readJson<NoteDetail>(`/api/notes/${noteId}`, { signal })' in api_source
    assert "export function listFolders(signal?: AbortSignal): Promise<Folder[]>" in api_source
    assert 'return readJson<Folder[]>("/api/folders", { signal })' in api_source
    assert "async function loadNoteScreenData(noteId: string, signal?: AbortSignal): Promise<{ note: NoteDetail; folders: Folder[] }>" in app_source
    assert "const [note, folders] = await Promise.all([getNoteDetail(noteId, signal), listFolders(signal)])" in app_source
    assert "loadNoteScreenData(noteId, controller.signal)" in app_source
    assert 'return { kind: "note", noteId: noteMatch[1] }' in app_source


def test_note_detail_screen_renders_note_fields_and_action_layout() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert '<span className="field-label">Title</span>' in app_source
    assert '<span className="field-label">Folder</span>' in app_source
    assert '<span className="field-label">Tags</span>' in app_source
    assert '<span className="field-label">Editor Content</span>' in app_source
    assert '<span className="field-label">Warnings</span>' in app_source
    assert '<span className="field-label">Processing Error</span>' in app_source
    assert 'className="action-button primary-action"' in app_source
    assert 'onClick={() => void handleSave()}' in app_source
    assert 'onClick={() => void handleReindex()}' in app_source
    assert 'onClick={() => void handleDelete()}' in app_source
    assert "Save" in app_source
    assert "Reindex" in app_source
    assert "Delete" in app_source
    assert "const serializedContentJson = JSON.stringify(editorContentJson, null, 2)" in app_source
    assert '<NoteEditor' in app_source
    assert 'noteId={note.id}' in app_source
    assert 'contentJson={editorContentJson}' in app_source
    assert 'onAutoConvertTag={handleAutoConvertTag}' in app_source
    assert 'onContentChange={setDraftContentJson}' in app_source


def test_note_detail_screen_surfaces_backend_error_message_for_unknown_note() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    api_source = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")

    assert "function toApiError(error: unknown): ApiError" in app_source
    assert '<p className="error-meta">Error code: {state.error.code}</p>' in app_source
    assert 'message: response.statusText || "Request failed"' in api_source
    assert 'async function readApiError(response: Response): Promise<ApiError>' in api_source
    assert 'throw await readApiError(response)' in api_source
