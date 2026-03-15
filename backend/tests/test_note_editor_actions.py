from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_note_editor_action_helpers_use_public_note_api_contracts() -> None:
    api_source = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")

    assert "export type AsyncAccepted = {" in api_source
    assert "export type NoteSavePayload = {" in api_source
    assert "export type SaveNoteResponse = NoteDetail | AsyncAccepted" in api_source
    assert "export function saveNote(noteId: string, payload: NoteSavePayload, signal?: AbortSignal): Promise<SaveNoteResponse>" in api_source
    assert 'return readJson<SaveNoteResponse>(`/api/notes/${noteId}`, {' in api_source
    assert 'method: "PATCH"' in api_source
    assert 'body: JSON.stringify(payload)' in api_source
    assert "export function reindexNote(noteId: string, signal?: AbortSignal): Promise<AsyncAccepted>" in api_source
    assert 'return readJson<AsyncAccepted>(`/api/notes/${noteId}/reindex`, {' in api_source
    assert 'method: "POST"' in api_source
    assert "export async function deleteNote(noteId: string, signal?: AbortSignal): Promise<void>" in api_source
    assert 'method: "DELETE"' in api_source


def test_note_editor_actions_wire_save_delete_and_reindex_from_local_screen_state() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'const [draftTitle, setDraftTitle] = useState("")' in app_source
    assert 'const [draftFolderId, setDraftFolderId] = useState<string | null>(null)' in app_source
    assert 'const [activeAction, setActiveAction] = useState<"saving" | "reindexing" | "deleting" | null>(null)' in app_source
    assert 'const response = await saveNote(note.id, {' in app_source
    assert 'title: draftTitle,' in app_source
    assert 'folder_id: draftFolderId,' in app_source
    assert 'tags: displayedTags,' in app_source
    assert 'content_json: editorContentJson,' in app_source
    assert 'const response = await reindexNote(note.id)' in app_source
    assert 'if (!window.confirm("Delete this note permanently?")) {' in app_source
    assert 'await deleteNote(note.id)' in app_source
    assert 'window.location.assign("/")' in app_source


def test_note_editor_actions_handle_async_acceptance_and_show_feedback() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    styles_source = (FRONTEND_SRC / "styles.css").read_text(encoding="utf-8")

    assert 'function isAsyncAccepted(response: NoteDetail | AsyncAccepted): response is AsyncAccepted {' in app_source
    assert 'if (isAsyncAccepted(response)) {' in app_source
    assert 'const refreshedNote = await refreshLoadedNote(folders)' in app_source
    assert 'setActionNotice({ tone: "success", message: response.message })' in app_source
    assert 'setActionNotice({ tone: "success", message: "Note saved without starting background processing." })' in app_source
    assert 'setActionNotice({ tone: "error", message: toApiError(error).message })' in app_source
    assert 'className={`action-notice ${actionNotice.tone === "error" ? "is-error" : "is-success"}`}' in app_source
    assert ".action-notice" in styles_source
    assert ".action-notice.is-success" in styles_source
    assert ".action-notice.is-error" in styles_source
