from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RankedSearchCandidate:
    note_id: UUID
    updated_at: datetime


@dataclass(frozen=True)
class FusedSearchCandidate:
    note_id: UUID
    score: float
    updated_at: datetime


def fuse_reciprocal_rank_search(
    *,
    lexical_candidates: list[RankedSearchCandidate],
    vector_candidates: list[RankedSearchCandidate],
    rrf_k: int,
) -> list[FusedSearchCandidate]:
    fused_scores: dict[UUID, FusedSearchCandidate] = {}

    for rank, candidate in enumerate(lexical_candidates, start=1):
        _merge_rrf_score(
            fused_scores,
            candidate=candidate,
            score_delta=1.0 / (rrf_k + rank),
        )

    for rank, candidate in enumerate(vector_candidates, start=1):
        _merge_rrf_score(
            fused_scores,
            candidate=candidate,
            score_delta=1.0 / (rrf_k + rank),
        )

    return sorted(
        fused_scores.values(),
        key=lambda candidate: (candidate.score, candidate.updated_at, candidate.note_id.int),
        reverse=True,
    )


def _merge_rrf_score(
    fused_scores: dict[UUID, FusedSearchCandidate],
    *,
    candidate: RankedSearchCandidate,
    score_delta: float,
) -> None:
    existing = fused_scores.get(candidate.note_id)
    if existing is None:
        fused_scores[candidate.note_id] = FusedSearchCandidate(
            note_id=candidate.note_id,
            score=score_delta,
            updated_at=candidate.updated_at,
        )
        return

    fused_scores[candidate.note_id] = FusedSearchCandidate(
        note_id=existing.note_id,
        score=existing.score + score_delta,
        updated_at=max(existing.updated_at, candidate.updated_at),
    )
