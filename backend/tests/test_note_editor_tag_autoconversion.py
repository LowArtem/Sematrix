from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_note_editor_has_shared_hashtag_autoconvert_guards() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'type TagAutoConvertRequest = {' in app_source
    assert 'const TAG_AUTO_CONVERT_PATTERN = /(^|[\\s([{])#([0-9A-Za-zА-Яа-яЁё_]+)$/' in app_source
    assert 'const TAG_AUTO_CONVERT_PUNCTUATION = new Set([",", ".", "!", "?", ";", ":", ")", "]"])' in app_source
    assert 'function getAutoConvertCompletionText(event: KeyboardEvent): string | null {' in app_source
    assert 'if (event.key === " ") {' in app_source
    assert 'if (event.key === "Enter") {' in app_source


def test_note_editor_autoconverts_tags_only_in_normal_text_and_moves_focus() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'handleKeyDown: (_view, event) => {' in app_source
    assert 'if (editor.isActive("link") || editor.isActive("code") || editor.isActive("codeBlock")) {' in app_source
    assert 'const match = textBeforeCursor.match(TAG_AUTO_CONVERT_PATTERN)' in app_source
    assert 'const normalizedTag = normalizeTagName(match[2])' in app_source
    assert 'tr.delete(deleteFrom, deleteTo)' in app_source
    assert 'tr.insertText(completionText, deleteFrom)' in app_source
    assert 'onAutoConvertTag({ normalizedTag, completionText })' in app_source
    assert 'const tagInputRef = useRef<HTMLInputElement | null>(null)' in app_source
    assert 'tagInputRef.current?.focus()' in app_source
    assert 'Type a valid #tag and finish with space, Enter, or punctuation to convert it into a note tag.' in app_source


def test_note_screen_merges_autoconverted_tags_through_shared_normalization() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'function handleAutoConvertTag({ normalizedTag }: TagAutoConvertRequest): void {' in app_source
    assert 'const tagWasAdded = !displayedTags.includes(normalizedTag)' in app_source
    assert 'setDraftTags((currentTags) => normalizeTagNames([...(currentTags ?? displayedTags), normalizedTag]))' in app_source
    assert 'setPendingAutoConvertRollback({ normalizedTag, tagWasAdded })' in app_source
    assert 'setTagInput("")' in app_source
    assert 'setTagError(null)' in app_source


def test_note_editor_exposes_latest_autoconversion_rollback_through_editor_undo() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'type TagAutoConvertRollbackHandle = {' in app_source
    assert 'const NoteEditor = forwardRef<TagAutoConvertRollbackHandle' in app_source
    assert 'const canRollbackAutoConvertRef = useRef(false)' in app_source
    assert 'rollbackLatestAutoConvert: () => {' in app_source
    assert 'return editor.chain().focus().undo().run()' in app_source
    assert 'if (canRollbackAutoConvertRef.current) {' in app_source
    assert 'onClearAutoConvertRollback()' in app_source


def test_tag_input_supports_ctrl_z_and_backspace_rollback_for_latest_autoconversion() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert 'const editorRef = useRef<TagAutoConvertRollbackHandle | null>(null)' in app_source
    assert 'function rollbackLatestAutoConvert(): void {' in app_source
    assert 'const rollbackApplied = editorRef.current?.rollbackLatestAutoConvert()' in app_source
    assert 'if (pendingAutoConvertRollback.tagWasAdded) {' in app_source
    assert 'if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z" && pendingAutoConvertRollback) {' in app_source
    assert 'if (event.key === "Backspace" && !tagInput && pendingAutoConvertRollback) {' in app_source
    assert 'clearPendingAutoConvertRollback()' in app_source
