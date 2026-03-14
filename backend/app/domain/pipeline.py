from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID


PROCESS_LINKS_TASK = "sematrix.process_links"
PROCESS_OCR_TASK = "sematrix.process_ocr"
PROCESS_IMAGE_CAPTION_TASK = "sematrix.process_image_caption"


@dataclass(frozen=True)
class PipelineStage:
    name: str
    task_name: str


def build_pipeline_stages(
    *,
    snapshot_asset_ids: list[UUID],
    snapshot_link_ids: list[UUID],
    disable_link_fetch: bool,
    disable_ocr: bool,
    disable_image_caption: bool,
) -> list[PipelineStage]:
    stages: list[PipelineStage] = []

    if snapshot_link_ids and not disable_link_fetch:
        stages.append(PipelineStage(name="process_links", task_name=PROCESS_LINKS_TASK))

    if snapshot_asset_ids and not disable_ocr:
        stages.append(PipelineStage(name="process_ocr", task_name=PROCESS_OCR_TASK))

    if snapshot_asset_ids and not disable_image_caption:
        stages.append(
            PipelineStage(
                name="process_image_caption",
                task_name=PROCESS_IMAGE_CAPTION_TASK,
            )
        )

    return stages


def compute_snapshot_hash(*, asset_ids: list[UUID], link_ids: list[UUID]) -> str:
    sorted_asset_ids = sorted(str(asset_id) for asset_id in asset_ids)
    sorted_link_ids = sorted(str(link_id) for link_id in link_ids)
    snapshot_payload = "|".join([*sorted_asset_ids, "--", *sorted_link_ids])
    return sha256(snapshot_payload.encode("utf-8")).hexdigest()
