from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_note_fts_source_uses_fixed_ru_en_tsquery_pattern() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert 'def build_note_search_tsquery(text_query: str):' in infra_source
    assert 'func.websearch_to_tsquery("russian", text_query).op("||")(' in infra_source
    assert 'func.websearch_to_tsquery("english", text_query)' in infra_source
    assert 'func.ts_rank_cd(Note.search_tsv, tsquery).label("lexical_rank")' in infra_source
    assert '.where(Note.search_tsv.op("@@")(tsquery))' in infra_source


def test_note_fts_source_orders_lexical_candidates_by_rank_then_recency() -> None:
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert 'normalized_text_query = " ".join(text_query.split())' in infra_source
    assert '.where(Note.id.in_(select(filtered_note_ids.c.id)))' in infra_source
    assert '.order_by(lexical_rank.desc(), Note.updated_at.desc(), Note.id.desc())' in infra_source
    assert 'LexicalSearchCandidateRecord(' in infra_source
