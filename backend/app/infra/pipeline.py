from __future__ import annotations

from uuid import UUID

from app.workers.tasks import start_pipeline


class CeleryPipelineDispatcher:
    def start_pipeline(self, *, note_id: UUID, index_version: int, request_id: str | None) -> None:
        start_pipeline.delay(
            note_id=str(note_id),
            index_version=index_version,
            request_id=request_id,
        )
