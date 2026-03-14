from typing import Protocol


class RuntimeMetadataReader(Protocol):
    def get_service_name(self) -> str:
        ...


class SystemStatusService:
    def __init__(self, runtime_metadata: RuntimeMetadataReader) -> None:
        self._runtime_metadata = runtime_metadata

    def read_root_payload(self) -> dict[str, str]:
        return {"service": self._runtime_metadata.get_service_name()}

    def read_health_payload(self) -> dict[str, str]:
        return {"status": "ok"}


class WorkerHeartbeatService:
    def ping(self) -> str:
        return "pong"
