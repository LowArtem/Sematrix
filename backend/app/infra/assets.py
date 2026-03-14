from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Protocol
import uuid

from sqlalchemy.orm import Session

from app.domain.errors import NotFoundError
from app.infra.models import Asset, Note, NoteAsset


CONTAINER_ASSETS_ROOT = Path("/data/assets")
MIME_TYPE_TO_EXTENSION = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


@dataclass(frozen=True)
class AssetRecord:
    id: uuid.UUID
    mime_type: str
    size_bytes: int


@dataclass(frozen=True)
class AssetFileRecord:
    path: Path
    mime_type: str
    filename: str


class AssetRepository(Protocol):
    def create_image_asset(
        self,
        *,
        note_id: uuid.UUID,
        filename: str | None,
        mime_type: str,
        content: bytes,
    ) -> AssetRecord: ...

    def get_asset_file(self, asset_id: uuid.UUID) -> AssetFileRecord: ...


def get_assets_root() -> Path:
    if CONTAINER_ASSETS_ROOT.exists():
        return CONTAINER_ASSETS_ROOT
    return Path(__file__).resolve().parents[3] / "data" / "assets"


def get_asset_path(storage_key: str) -> Path:
    return get_assets_root() / storage_key


class SqlAlchemyAssetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_image_asset(
        self,
        *,
        note_id: uuid.UUID,
        filename: str | None,
        mime_type: str,
        content: bytes,
    ) -> AssetRecord:
        note = self._session.get(Note, note_id)
        if note is None:
            raise NotFoundError("Note not found")

        storage_key = self._build_storage_key(mime_type)
        asset_path = get_asset_path(storage_key)
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        asset_path.write_bytes(content)

        asset = Asset(
            storage_key=storage_key,
            original_filename=self._normalize_filename(filename=filename, mime_type=mime_type),
            mime_type=mime_type,
            file_ext=MIME_TYPE_TO_EXTENSION[mime_type],
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

        try:
            self._session.add(asset)
            self._session.flush()
            self._session.add(NoteAsset(note_id=note.id, asset_id=asset.id))
            self._session.commit()
        except Exception:
            self._session.rollback()
            asset_path.unlink(missing_ok=True)
            raise

        return AssetRecord(id=asset.id, mime_type=asset.mime_type, size_bytes=asset.size_bytes)

    def get_asset_file(self, asset_id: uuid.UUID) -> AssetFileRecord:
        asset = self._session.get(Asset, asset_id)
        if asset is None:
            raise NotFoundError("Asset not found")

        asset_path = get_asset_path(asset.storage_key)
        if not asset_path.exists():
            raise NotFoundError("Asset not found")

        return AssetFileRecord(
            path=asset_path,
            mime_type=asset.mime_type,
            filename=asset.original_filename,
        )

    @staticmethod
    def _build_storage_key(mime_type: str) -> str:
        return f"{uuid.uuid4().hex}{MIME_TYPE_TO_EXTENSION[mime_type]}"

    @staticmethod
    def _normalize_filename(*, filename: str | None, mime_type: str) -> str:
        candidate = Path(filename or "").name.strip()
        if candidate:
            return candidate
        return f"image{MIME_TYPE_TO_EXTENSION[mime_type]}"
