from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPO_ROOT / "frontend"


def test_frontend_declares_tiptap_dependencies() -> None:
    package_source = (FRONTEND_ROOT / "package.json").read_text(encoding="utf-8")

    assert '"@tiptap/react": "2.7.1"' in package_source
    assert '"@tiptap/starter-kit": "2.7.1"' in package_source
    assert '"@tiptap/extension-link": "2.7.1"' in package_source
    assert '"@tiptap/extension-image": "2.7.1"' in package_source


def test_note_screen_configures_minimum_tiptap_feature_set() -> None:
    app_source = (FRONTEND_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")

    assert 'import { EditorContent, useEditor } from "@tiptap/react"' in app_source
    assert 'import StarterKit from "@tiptap/starter-kit"' in app_source
    assert 'import Link from "@tiptap/extension-link"' in app_source
    assert 'import Image from "@tiptap/extension-image"' in app_source
    assert "StarterKit" in app_source
    assert "toggleBold()" in app_source
    assert "toggleItalic()" in app_source
    assert "toggleBulletList()" in app_source
    assert "toggleOrderedList()" in app_source
    assert "toggleHeading({ level: 1 })" in app_source
    assert "toggleHeading({ level: 2 })" in app_source
    assert "toggleBlockquote()" in app_source
    assert "toggleCodeBlock()" in app_source
    assert 'setLink({ href: trimmedUrl })' in app_source
    assert "Image.configure({" in app_source
    assert "inline: true" in app_source
    assert "<EditorContent editor={editor} className=\"tiptap-shell\" />" in app_source


def test_note_screen_serializes_tiptap_document_back_to_content_json() -> None:
    app_source = (FRONTEND_ROOT / "src" / "App.tsx").read_text(encoding="utf-8")

    assert "onContentChange(nextEditor.getJSON() as Record<string, unknown>)" in app_source
    assert "editor.commands.setContent(contentJson, false)" in app_source
    assert "const serializedContentJson = JSON.stringify(editorContentJson, null, 2)" in app_source
    assert "<textarea className=\"editor-surface\" value={serializedContentJson} readOnly />" in app_source
