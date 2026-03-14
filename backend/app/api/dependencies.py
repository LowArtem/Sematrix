from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.domain.folders import FolderService
from app.domain.system import SystemStatusService
from app.infra import SessionLocal
from app.infra.folders import SqlAlchemyFolderRepository
from app.infra.system import RuntimeMetadataRepository


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
