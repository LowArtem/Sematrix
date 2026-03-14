from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import get_asset_service
from app.api.dto import AssetDto
from app.domain.assets import AssetService


api_assets_router = APIRouter(prefix="/assets", tags=["assets"])


@api_assets_router.post("/image", response_model=AssetDto, status_code=status.HTTP_201_CREATED)
async def upload_image(
    note_id: UUID | None = Form(default=None),
    file: UploadFile = File(...),
    service: AssetService = Depends(get_asset_service),
) -> AssetDto:
    try:
        asset = service.upload_image(
            note_id=note_id,
            filename=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            content=await file.read(),
        )
    finally:
        await file.close()

    return AssetDto(
        id=asset.id,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        url=asset.url,
    )


@api_assets_router.get("/{asset_id}")
def get_asset(asset_id: UUID, service: AssetService = Depends(get_asset_service)) -> FileResponse:
    asset_file = service.get_asset_file(asset_id)
    return FileResponse(
        path=asset_file.path,
        media_type=asset_file.mime_type,
        filename=asset_file.filename,
    )
