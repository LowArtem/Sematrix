from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_note_grid_uses_backend_limit_offset_pagination() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'const [paginationOffset, setPaginationOffset] = useState(0)' in app_source
    assert "offset: paginationOffset" in app_source
    assert 'setPaginationOffset(0)' in app_source
    assert 'Page {currentPage} of {totalPages}' in app_source
    assert 'disabled={!hasPreviousPage}' in app_source
    assert 'disabled={!hasNextPage}' in app_source


def test_note_cards_render_backend_note_fields_without_client_ranking() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    style_source = (FRONTEND_SRC / "styles.css").read_text(encoding="utf-8")

    assert 'className="note-grid"' in app_source
    assert 'className="note-card"' in app_source
    assert 'buildCardSummary(note)' in app_source
    assert 'className="tag-list"' in app_source
    assert 'className={buildStatusClassName(note.status)}' in app_source
    assert 'grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));' in style_source


def test_note_cards_show_backend_status_badges_and_ready_warning_indicator() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    style_source = (FRONTEND_SRC / "styles.css").read_text(encoding="utf-8")

    assert 'function buildStatusClassName(status: string): string {' in app_source
    assert 'return `status-pill status-${status.toLowerCase()}`' in app_source
    assert 'note.status === "Ready" && note.has_warnings ? (' in app_source
    assert 'className="warning-pill"' in app_source
    assert 'buildWarningLabel(note.warnings_count)' in app_source
    assert '.status-draft {' in style_source
    assert '.status-processing {' in style_source
    assert '.status-ready {' in style_source
    assert '.status-error {' in style_source
    assert '.warning-pill {' in style_source
