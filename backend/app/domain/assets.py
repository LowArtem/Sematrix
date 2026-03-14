from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.domain.errors import BadRequestError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.infra.assets import AssetFileRecord, AssetRecord, AssetRepository


ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
}


@dataclass(frozen=True)
class AssetResult:
    id: UUID
    mime_type: str
    size_bytes: int
    url: str


@dataclass(frozen=True)
class AssetFileResult:
    path: Path
    mime_type: str
    filename: str


class AssetService:
    def __init__(self, asset_repository: AssetRepository, *, max_image_mb: int) -> None:
        self._asset_repository = asset_repository
        self._max_image_bytes = max_image_mb * 1024 * 1024

    def upload_image(
        self,
        *,
        note_id: UUID | None,
        filename: str | None,
        mime_type: str,
        content: bytes,
    ) -> AssetResult:
        if note_id is None:
            raise BadRequestError("note_id is required")

        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            raise UnsupportedMediaTypeError("Only PNG, JPEG, and WebP images are supported")

        if len(content) > self._max_image_bytes:
            raise PayloadTooLargeError("Image file exceeds MAX_IMAGE_MB")

        asset = self._asset_repository.create_image_asset(
            note_id=note_id,
            filename=filename,
            mime_type=mime_type,
            content=content,
        )
        return self._to_result(asset)

    def get_asset_file(self, asset_id: UUID) -> AssetFileResult:
        asset_file = self._asset_repository.get_asset_file(asset_id)
        return AssetFileResult(
            path=asset_file.path,
            mime_type=asset_file.mime_type,
            filename=asset_file.filename,
        )

    @staticmethod
    def _to_result(asset: AssetRecord) -> AssetResult:
        return AssetResult(
            id=asset.id,
            mime_type=asset.mime_type,
            size_bytes=asset.size_bytes,
            url=f"/api/assets/{asset.id}",
        )
