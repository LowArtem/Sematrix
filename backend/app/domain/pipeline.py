from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID


PROCESS_LINKS_TASK = "sematrix.process_links"
PROCESS_OCR_TASK = "sematrix.process_ocr"
PROCESS_IMAGE_CAPTION_TASK = "sematrix.process_image_caption"
NOTE_EMBEDDING_DIMENSION = 1024
TASK_STAGE_NAME_MAP = {
    PROCESS_LINKS_TASK: "process_links",
    PROCESS_OCR_TASK: "process_ocr",
    PROCESS_IMAGE_CAPTION_TASK: "process_image_caption",
}
NORMALIZED_STAGE_NAME_MAP = {
    "process_links": "link_fetch",
    "process_ocr": "ocr",
    "process_image_caption": "image_caption",
}
NON_CRITICAL_PIPELINE_STAGES = frozenset(NORMALIZED_STAGE_NAME_MAP.values())


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


def build_search_text(
    *,
    title: str,
    content_text_flat: str,
    tag_names: list[str],
    asset_texts: list[str],
    link_texts: list[str],
) -> str:
    parts: list[str] = []

    normalized_title = title.strip()
    if normalized_title:
        parts.append(normalized_title)

    normalized_content = content_text_flat.strip()
    if normalized_content:
        parts.append(normalized_content)

    if tag_names:
        parts.append(" ".join(f"#{tag_name}" for tag_name in tag_names))

    for text in [*asset_texts, *link_texts]:
        normalized_text = text.strip()
        if normalized_text:
            parts.append(normalized_text)

    return "\n\n".join(parts)


def validate_note_embedding(embedding: list[float]) -> None:
    if len(embedding) != NOTE_EMBEDDING_DIMENSION:
        raise ValueError(
            f"Embedding dimensionality must be exactly {NOTE_EMBEDDING_DIMENSION}"
        )


def normalize_pipeline_stage_name(stage_name: str | None) -> str | None:
    if stage_name is None:
        return None

    task_stage_name = TASK_STAGE_NAME_MAP.get(stage_name, stage_name)
    return NORMALIZED_STAGE_NAME_MAP.get(task_stage_name, task_stage_name)


def is_noncritical_pipeline_stage(stage_name: str | None) -> bool:
    normalized_stage_name = normalize_pipeline_stage_name(stage_name)
    return normalized_stage_name in NON_CRITICAL_PIPELINE_STAGES


def build_processing_warning(
    *,
    stage: str,
    target: str,
    code: str,
    message: str,
    retryable: bool,
) -> dict[str, object]:
    return {
        "stage": stage,
        "target": target,
        "code": code,
        "message": message,
        "retryable": retryable,
    }


def merge_processing_warnings(*warning_groups: list[dict[str, object]]) -> list[dict[str, object]]:
    merged_warnings: list[dict[str, object]] = []
    seen_warnings: set[tuple[str, str, str, str, bool]] = set()

    for warning_group in warning_groups:
        for warning in warning_group:
            warning_key = (
                str(warning.get("stage", "")),
                str(warning.get("target", "")),
                str(warning.get("code", "")),
                str(warning.get("message", "")),
                bool(warning.get("retryable", False)),
            )
            if warning_key in seen_warnings:
                continue
            seen_warnings.add(warning_key)
            merged_warnings.append(
                build_processing_warning(
                    stage=warning_key[0],
                    target=warning_key[1],
                    code=warning_key[2],
                    message=warning_key[3],
                    retryable=warning_key[4],
                )
            )

    return merged_warnings
