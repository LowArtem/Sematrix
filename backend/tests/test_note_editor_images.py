from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


def test_frontend_declares_image_upload_api_helper() -> None:
    api_source = (FRONTEND_SRC / "api.ts").read_text(encoding="utf-8")

    assert "export type Asset = {" in api_source
    assert "export function uploadImage(noteId: string, file: File, signal?: AbortSignal): Promise<Asset>" in api_source
    assert 'formData.append("note_id", noteId)' in api_source
    assert 'formData.append("file", file)' in api_source
    assert 'return readJson<Asset>("/api/assets/image", {' in api_source


def test_note_editor_reuses_one_assetid_image_node_for_all_insert_flows() -> None:
    app_source = (FRONTEND_SRC / "App.tsx").read_text(encoding="utf-8")

    assert "const AssetImage = Image.extend({" in app_source
    assert 'parseHTML: (element) => element.getAttribute("data-asset-id")' in app_source
    assert 'return { "data-asset-id": String(attributes.assetId) }' in app_source
    assert '.setImage({ src: asset.url, alt: assetAlt, assetId: asset.id })' in app_source
    assert 'const imageFiles = extractImageFiles(event.clipboardData?.files ?? null)' in app_source
    assert 'const imageFiles = extractImageFiles(event.dataTransfer?.files ?? null)' in app_source
    assert 'const imageFiles = extractImageFiles(event.target.files)' in app_source
    assert 'const asset = await uploadImage(noteId, imageFile)' in app_source
    assert 'label="Image"' in app_source
    assert 'accept="image/png,image/jpeg,image/webp,image/*"' in app_source
