from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_frontend_tag_helper_mirrors_backend_normalization_rules() -> None:
    tag_source = (FRONTEND_SRC / "tags.ts").read_text(encoding="utf-8")

    assert "const TAG_NAME_PATTERN = /^[0-9A-Za-zА-Яа-яЁё_]+$/" in tag_source
    assert 'const normalized = value.trim().toLowerCase()' in tag_source
    assert 'throw new Error("Tag name cannot contain spaces")' in tag_source
    assert "Tag name may contain only Latin/Cyrillic letters, digits, and underscore" in tag_source
    assert "if (seen.has(normalized)) {" in tag_source


def test_note_screen_has_manual_tag_input_and_remove_controls() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")
    style_source = (FRONTEND_SRC / "styles.css").read_text(encoding="utf-8")

    assert 'const [draftTags, setDraftTags] = useState<string[] | null>(null)' in app_source
    assert 'const [tagInput, setTagInput] = useState("")' in app_source
    assert 'const [tagError, setTagError] = useState<string | null>(null)' in app_source
    assert 'const displayedTags = draftTags ?? normalizeTagNames(note.tags.map((tag) => tag.name))' in app_source
    assert 'const normalizedTag = normalizeTagName(tagInput)' in app_source
    assert 'setDraftTags((currentTags) => [...(currentTags ?? []), normalizedTag])' in app_source
    assert 'setDraftTags((currentTags) => (currentTags ?? []).filter((currentTag) => currentTag !== tagName))' in app_source
    assert 'placeholder="Add a tag like research_notes"' in app_source
    assert 'className="tag-chip tag-chip-button"' in app_source
    assert 'type="button"' in app_source
    assert 'onClick={() => handleRemoveTag(tagName)}' in app_source
    assert 'Tags are trimmed, lowercased, and may use Latin/Cyrillic letters, digits, and underscore.' in app_source
    assert ".tag-chip-button {" in style_source
    assert ".tag-editor-row {" in style_source
    assert ".field-error {" in style_source
