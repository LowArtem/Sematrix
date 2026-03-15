from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
from uuid import UUID


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def _load_search_module():
    module_path = BACKEND_APP / "domain" / "search.py"
    spec = importlib.util.spec_from_file_location("test_note_search_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load app.domain.search")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SEARCH_MODULE = _load_search_module()
RankedSearchCandidate = SEARCH_MODULE.RankedSearchCandidate
fuse_reciprocal_rank_search = SEARCH_MODULE.fuse_reciprocal_rank_search


def _candidate(note_id: str, updated_at: datetime) -> RankedSearchCandidate:
    return RankedSearchCandidate(note_id=UUID(note_id), updated_at=updated_at)


def test_rrf_combines_lexical_and_vector_ranks() -> None:
    updated_at = datetime(2026, 3, 15, tzinfo=timezone.utc)
    fused_candidates = fuse_reciprocal_rank_search(
        lexical_candidates=[
            _candidate("00000000-0000-0000-0000-000000000001", updated_at),
            _candidate("00000000-0000-0000-0000-000000000002", updated_at),
        ],
        vector_candidates=[
            _candidate("00000000-0000-0000-0000-000000000002", updated_at),
            _candidate("00000000-0000-0000-0000-000000000003", updated_at),
        ],
        rrf_k=60,
    )

    assert [str(candidate.note_id) for candidate in fused_candidates] == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000003",
    ]
    assert fused_candidates[0].score == (1 / 62) + (1 / 61)


def test_rrf_uses_updated_at_then_id_as_tie_breakers() -> None:
    fused_candidates = fuse_reciprocal_rank_search(
        lexical_candidates=[
            _candidate("00000000-0000-0000-0000-000000000001", datetime(2026, 3, 15, 10, tzinfo=timezone.utc)),
            _candidate("00000000-0000-0000-0000-000000000002", datetime(2026, 3, 15, 10, tzinfo=timezone.utc)),
        ],
        vector_candidates=[],
        rrf_k=60,
    )

    assert [str(candidate.note_id) for candidate in fused_candidates] == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]

    tied_candidates = fuse_reciprocal_rank_search(
        lexical_candidates=[
            _candidate("00000000-0000-0000-0000-000000000001", datetime(2026, 3, 15, 10, tzinfo=timezone.utc)),
        ],
        vector_candidates=[
            _candidate("00000000-0000-0000-0000-000000000002", datetime(2026, 3, 15, 10, tzinfo=timezone.utc)),
        ],
        rrf_k=60,
    )

    assert [str(candidate.note_id) for candidate in tied_candidates] == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000001",
    ]


def test_rrf_scores_are_stable_before_pagination() -> None:
    updated_at = datetime(2026, 3, 15, tzinfo=timezone.utc)
    fused_candidates = fuse_reciprocal_rank_search(
        lexical_candidates=[
            _candidate("00000000-0000-0000-0000-000000000001", updated_at),
            _candidate("00000000-0000-0000-0000-000000000002", updated_at),
            _candidate("00000000-0000-0000-0000-000000000003", updated_at),
        ],
        vector_candidates=[
            _candidate("00000000-0000-0000-0000-000000000003", updated_at),
            _candidate("00000000-0000-0000-0000-000000000001", updated_at),
            _candidate("00000000-0000-0000-0000-000000000004", updated_at),
        ],
        rrf_k=60,
    )

    first_page = [str(candidate.note_id) for candidate in fused_candidates[:2]]
    second_page = [str(candidate.note_id) for candidate in fused_candidates[2:4]]

    assert first_page == [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000003",
    ]
    assert second_page == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000004",
    ]


def test_hybrid_note_list_source_uses_same_rrf_topn_for_both_candidate_lists() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")

    assert "limit=self._rrf_topn" in domain_source
    assert "self._note_repository.list_lexical_search_candidates(" in domain_source
    assert "self._note_repository.list_vector_search_candidates(" in domain_source
    assert "query_embedding = self._semantic_search_client.embed_text(text=text_query)" in domain_source
    assert "fuse_reciprocal_rank_search(" in domain_source
    assert "paginated_candidates = fused_candidates[offset : offset + limit]" in domain_source
    assert "total=len(fused_candidates)" in domain_source


def test_vector_search_repository_source_uses_pgvector_distance_without_ann_specifics() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert 'vector_distance = Note.embedding.cosine_distance(query_embedding).label("vector_distance")' in infra_source
    assert ".where(Note.embedding.is_not(None))" in infra_source
    assert ".order_by(vector_distance.asc(), Note.updated_at.desc(), Note.id.desc())" in infra_source
    assert "ivfflat" not in infra_source.lower()
    assert "hnsw" not in infra_source.lower()
