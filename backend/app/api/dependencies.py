from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core import get_settings
from app.domain.assets import AssetService
from app.domain.folders import FolderService
from app.domain.notes import NoteService
from app.domain.system import SystemStatusService
from app.domain.tags import TagService
from app.infra import SessionLocal
from app.infra.assets import SqlAlchemyAssetRepository
from app.infra.folders import SqlAlchemyFolderRepository
from app.infra.notes import SqlAlchemyNoteRepository
from app.infra.pipeline import CeleryPipelineDispatcher
from app.infra.system import RuntimeMetadataRepository
from app.infra.tags import SqlAlchemyTagRepository


def get_system_status_service() -> SystemStatusService:
    return SystemStatusService(runtime_metadata=RuntimeMetadataRepository())


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_folder_service(session: Session = Depends(get_db_session)) -> FolderService:
    return FolderService(folder_repository=SqlAlchemyFolderRepository(session=session))


def get_tag_service(session: Session = Depends(get_db_session)) -> TagService:
    return TagService(tag_repository=SqlAlchemyTagRepository(session=session))


def get_asset_service(session: Session = Depends(get_db_session)) -> AssetService:
    return AssetService(
        asset_repository=SqlAlchemyAssetRepository(session=session),
        max_image_mb=get_settings().max_image_mb,
    )


def get_note_service(session: Session = Depends(get_db_session)) -> NoteService:
    return NoteService(
        note_repository=SqlAlchemyNoteRepository(session=session),
        pipeline_dispatcher=CeleryPipelineDispatcher(),
    )
