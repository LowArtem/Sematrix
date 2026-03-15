from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_frontend_search_files_exist() -> None:
    expected_paths = [
        FRONTEND_SRC / "App.tsx",
        FRONTEND_SRC / "api.ts",
        FRONTEND_SRC / "styles.css",
    ]

    missing = [path.relative_to(REPO_ROOT).as_posix() for path in expected_paths if not path.exists()]

    assert missing == []


def test_notes_api_helper_preserves_raw_q_and_backend_contract() -> None:
    api_source = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")

    assert 'searchParams.set("q", params.q)' in api_source
    assert 'searchParams.set("limit", String(params.limit))' in api_source
    assert 'searchParams.set("offset", String(params.offset))' in api_source
    assert 'searchParams.set("folder_id", params.folderId)' in api_source
    assert 'return `/api/notes?${searchParams.toString()}`' in api_source
    assert 'const response = await fetch(buildNotesRequestPath(params), {' in api_source


def test_app_uses_search_form_without_frontend_query_parsing() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'const [queryInput, setQueryInput] = useState("")' in app_source
    assert 'const [submittedQuery, setSubmittedQuery] = useState("")' in app_source
    assert 'setSubmittedQuery(queryInput)' in app_source
    assert 'fetchNotes(' in app_source
    assert 'placeholder="Search notes or type #tags"' in app_source
    assert 'The raw query is sent straight to <code>/api/notes</code>' in app_source
