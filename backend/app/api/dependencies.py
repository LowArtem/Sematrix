from app.domain.system import SystemStatusService
from app.infra.system import RuntimeMetadataRepository


def get_system_status_service() -> SystemStatusService:
    return SystemStatusService(runtime_metadata=RuntimeMetadataRepository())
