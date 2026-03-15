from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.domain.errors import NotFoundError
from app.domain.note_content import ExtractedLink, parse_note_content
from app.domain.note_lifecycle import build_draft_reset_state
from app.domain.note_lifecycle import has_meaningful_content
from app.domain.pipeline import compute_snapshot_hash
from app.infra.assets import get_asset_path
from app.infra.models import Asset, Folder, Note, NoteAsset, NoteLink, NoteTag, PipelineRun, Tag


EMPTY_DOCUMENT = {"type": "doc", "content": []}


@dataclass(frozen=True)
class NoteRecord:
    id: UUID
    created_at: datetime
    updated_at: datetime
    title: str
    summary: str
    folder_id: UUID | None
    tags: list[dict[str, Any]]
    content_json: dict[str, Any]
    status: str
    processing_error: str | None
    has_warnings: bool
    warnings_count: int
    processing_warnings: list[dict[str, Any]]
    index_version: int
    score: float | None = None


@dataclass(frozen=True)
class NoteListRecord:
    items: list[NoteRecord]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class LexicalSearchCandidateRecord:
    note_id: UUID
    lexical_rank: float
    updated_at: datetime


@dataclass(frozen=True)
class VectorSearchCandidateRecord:
    note_id: UUID
    updated_at: datetime


@dataclass(frozen=True)
class SaveNoteRecord:
    note: NoteRecord
    pipeline_started: bool
    pipeline_run: PipelineRunRecord | None


@dataclass(frozen=True)
class PipelineRunRecord:
    id: UUID
    note_id: UUID
    index_version: int
    started_at: datetime


@dataclass(frozen=True)
class ReindexNoteRecord:
    note: NoteRecord
    pipeline_run: PipelineRunRecord


@dataclass(frozen=True)
class DraftCleanupRecord:
    candidate_count: int
    deleted_draft_count: int
    deleted_asset_count: int
    deletion_errors: list[str]


class NoteRepository(Protocol):
    def create_note(self) -> NoteRecord: ...

    def get_note(self, note_id: UUID) -> NoteRecord | None: ...

    def delete_note(self, note_id: UUID) -> None: ...

    def reindex_note(self, note_id: UUID, *, request_id: str | None) -> ReindexNoteRecord: ...

    def cleanup_expired_empty_drafts(self, *, ttl_hours: int) -> DraftCleanupRecord: ...

    def save_note(
        self,
        *,
        note_id: UUID,
        title: str,
        folder_id: UUID | None,
        tag_names: list[str],
        content_json: dict[str, Any],
        content_text_flat: str,
        asset_ids: list[UUID],
        links: list[ExtractedLink],
        should_start_processing: bool,
        search_text: str,
        summary: str,
        processing_warnings: list[dict[str, object]],
        request_id: str | None,
    ) -> SaveNoteRecord: ...

    def list_notes(
        self,
        *,
        text_query: str,
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
        offset: int,
    ) -> NoteListRecord: ...

    def list_lexical_search_candidates(
        self,
        *,
        text_query: str,
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
    ) -> list[LexicalSearchCandidateRecord]: ...

    def list_vector_search_candidates(
        self,
        *,
        query_embedding: list[float],
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
    ) -> list[VectorSearchCandidateRecord]: ...

    def list_notes_by_ids(self, note_ids: list[UUID]) -> list[NoteRecord]: ...


def build_note_search_tsquery(text_query: str):
    return func.websearch_to_tsquery("russian", text_query).op("||")(
        func.websearch_to_tsquery("english", text_query)
    )


class SqlAlchemyNoteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_note(self) -> NoteRecord:
        note = Note(content_json=EMPTY_DOCUMENT)
        self._session.add(note)
        self._session.commit()
        self._session.refresh(note)
        return self._to_record(note)

    def get_note(self, note_id: UUID) -> NoteRecord | None:
        note = self._get_note_with_relations(note_id)
        if note is None:
            return None
        return self._to_record(note)

    def delete_note(self, note_id: UUID) -> None:
        note = self._get_note_for_delete(note_id)
        if note is None:
            raise NotFoundError("Note not found")

        asset_storage_keys_to_delete = self._delete_note_entity(note)
        self._session.commit()

        for storage_key in asset_storage_keys_to_delete:
            get_asset_path(storage_key).unlink(missing_ok=True)

    def cleanup_expired_empty_drafts(self, *, ttl_hours: int) -> DraftCleanupRecord:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        expired_drafts = list(
            self._session.scalars(
                select(Note)
                .where(Note.status == "Draft", Note.updated_at <= cutoff)
                .options(selectinload(Note.assets))
            )
        )

        expired_draft_ids: list[UUID] = []
        deletion_errors: list[str] = []

        for note in expired_drafts:
            try:
                if self._is_empty_draft_candidate(note):
                    expired_draft_ids.append(note.id)
            except Exception as exc:
                deletion_errors.append(f"{note.id}: {exc}")

        deleted_draft_count = 0
        deleted_asset_count = 0

        for note_id in expired_draft_ids:
            try:
                note = self._get_note_for_delete(note_id)
                if note is None:
                    continue

                asset_storage_keys_to_delete = self._delete_note_entity(note)
                self._session.commit()

                for storage_key in asset_storage_keys_to_delete:
                    get_asset_path(storage_key).unlink(missing_ok=True)

                deleted_draft_count += 1
                deleted_asset_count += len(asset_storage_keys_to_delete)
            except Exception as exc:
                self._session.rollback()
                deletion_errors.append(f"{note_id}: {exc}")

        return DraftCleanupRecord(
            candidate_count=len(expired_draft_ids),
            deleted_draft_count=deleted_draft_count,
            deleted_asset_count=deleted_asset_count,
            deletion_errors=deletion_errors,
        )

    def reindex_note(self, note_id: UUID, *, request_id: str | None) -> ReindexNoteRecord:
        note = self._get_note_with_relations(note_id)
        if note is None:
            raise NotFoundError("Note not found")

        note.index_version += 1
        note.status = "Processing"
        note.processing_error = None
        note.has_warnings = False
        note.warnings_count = 0
        note.processing_warnings = []

        self._session.add(note)
        pipeline_run = self._create_pipeline_run(
            note_id=note.id,
            index_version=note.index_version,
            request_id=request_id,
        )
        self._session.commit()

        reindexed_note = self._get_note_with_relations(note_id)
        if reindexed_note is None:
            raise NotFoundError("Note not found")

        return ReindexNoteRecord(note=self._to_record(reindexed_note), pipeline_run=pipeline_run)

    def save_note(
        self,
        *,
        note_id: UUID,
        title: str,
        folder_id: UUID | None,
        tag_names: list[str],
        content_json: dict[str, Any],
        content_text_flat: str,
        asset_ids: list[UUID],
        links: list[ExtractedLink],
        should_start_processing: bool,
        search_text: str,
        summary: str,
        processing_warnings: list[dict[str, object]],
        request_id: str | None,
    ) -> SaveNoteRecord:
        note = self._get_note_with_relations(note_id)
        if note is None:
            raise NotFoundError("Note not found")

        if folder_id is not None and self._session.get(Folder, folder_id) is None:
            raise NotFoundError("Folder not found")

        assets = self._get_assets(asset_ids)
        tags = self._get_or_create_tags(tag_names)

        note.title = title
        note.folder_id = folder_id
        note.content_json = content_json
        note.content_text_flat = content_text_flat
        note.tags = tags
        note.assets = assets
        self._sync_note_links(note=note, links=links)
        note.updated_at = datetime.now(timezone.utc)
        self._session.flush()

        pipeline_run: PipelineRunRecord | None = None

        if should_start_processing:
            note.index_version += 1
            note.status = "Processing"
            note.search_text = search_text
            note.summary = summary
            note.processing_error = None
            note.has_warnings = bool(processing_warnings)
            note.warnings_count = len(processing_warnings)
            note.processing_warnings = processing_warnings
            pipeline_run = self._create_pipeline_run(
                note_id=note.id,
                index_version=note.index_version,
                request_id=request_id,
            )
        else:
            draft_reset_state = build_draft_reset_state()
            note.status = "Draft"
            note.summary = draft_reset_state.summary
            note.search_text = draft_reset_state.search_text
            note.embedding = draft_reset_state.embedding
            note.processing_error = draft_reset_state.processing_error
            note.has_warnings = draft_reset_state.has_warnings
            note.warnings_count = draft_reset_state.warnings_count
            note.processing_warnings = draft_reset_state.processing_warnings

        self._session.add(note)
        self._session.commit()

        saved_note = self._get_note_with_relations(note_id)
        if saved_note is None:
            raise NotFoundError("Note not found")

        return SaveNoteRecord(
            note=self._to_record(saved_note),
            pipeline_started=should_start_processing,
            pipeline_run=pipeline_run,
        )

    def list_notes(
        self,
        *,
        text_query: str,
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
        offset: int,
    ) -> NoteListRecord:
        note_ids_query = self._build_filtered_note_ids_query(folder_id=folder_id, tag_names=tag_names)

        if text_query:
            pattern = f"%{text_query}%"
            note_ids_query = note_ids_query.where(
                or_(
                    Note.title.ilike(pattern),
                    Note.summary.ilike(pattern),
                    Note.search_text.ilike(pattern),
                    Note.content_text_flat.ilike(pattern),
                )
            )

        note_ids_subquery = note_ids_query.subquery()
        total = self._session.scalar(select(func.count()).select_from(note_ids_subquery)) or 0

        notes = list(
            self._session.scalars(
                select(Note)
                .where(Note.id.in_(select(note_ids_subquery.c.id)))
                .options(selectinload(Note.tags))
                .order_by(Note.updated_at.desc(), Note.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )

        return NoteListRecord(
            items=[self._to_record(note) for note in notes],
            total=total,
            limit=limit,
            offset=offset,
        )

    def list_lexical_search_candidates(
        self,
        *,
        text_query: str,
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
    ) -> list[LexicalSearchCandidateRecord]:
        normalized_text_query = " ".join(text_query.split())
        if not normalized_text_query:
            return []

        filtered_note_ids = self._build_filtered_note_ids_query(folder_id=folder_id, tag_names=tag_names).subquery()
        tsquery = build_note_search_tsquery(normalized_text_query)
        lexical_rank = func.ts_rank_cd(Note.search_tsv, tsquery).label("lexical_rank")
        rows = self._session.execute(
            select(Note.id, lexical_rank, Note.updated_at)
            .where(Note.id.in_(select(filtered_note_ids.c.id)))
            .where(Note.search_tsv.op("@@")(tsquery))
            .order_by(lexical_rank.desc(), Note.updated_at.desc(), Note.id.desc())
            .limit(limit)
        )

        return [
            LexicalSearchCandidateRecord(
                note_id=row.id,
                lexical_rank=float(row.lexical_rank),
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def list_vector_search_candidates(
        self,
        *,
        query_embedding: list[float],
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
    ) -> list[VectorSearchCandidateRecord]:
        if not query_embedding:
            return []

        filtered_note_ids = self._build_filtered_note_ids_query(folder_id=folder_id, tag_names=tag_names).subquery()
        vector_distance = Note.embedding.cosine_distance(query_embedding).label("vector_distance")
        rows = self._session.execute(
            select(Note.id, Note.updated_at, vector_distance)
            .where(Note.id.in_(select(filtered_note_ids.c.id)))
            .where(Note.embedding.is_not(None))
            .order_by(vector_distance.asc(), Note.updated_at.desc(), Note.id.desc())
            .limit(limit)
        )

        return [
            VectorSearchCandidateRecord(
                note_id=row.id,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def list_notes_by_ids(self, note_ids: list[UUID]) -> list[NoteRecord]:
        if not note_ids:
            return []

        notes = list(
            self._session.scalars(
                select(Note)
                .where(Note.id.in_(note_ids))
                .options(selectinload(Note.tags))
            )
        )
        return [self._to_record(note) for note in notes]

    def _get_note_with_relations(self, note_id: UUID) -> Note | None:
        return self._session.scalar(
            select(Note)
            .where(Note.id == note_id)
            .options(selectinload(Note.tags), selectinload(Note.assets), selectinload(Note.links))
        )

    @staticmethod
    def _build_filtered_note_ids_query(*, folder_id: UUID | None, tag_names: list[str]):
        note_ids_query = select(Note.id)

        if folder_id is not None:
            note_ids_query = note_ids_query.where(Note.folder_id == folder_id)

        if tag_names:
            note_ids_query = (
                note_ids_query.join(NoteTag, NoteTag.note_id == Note.id)
                .join(Tag, Tag.id == NoteTag.tag_id)
                .where(Tag.name.in_(tag_names))
                .group_by(Note.id)
                .having(func.count(func.distinct(Tag.name)) == len(tag_names))
            )

        return note_ids_query

    def _get_note_for_delete(self, note_id: UUID) -> Note | None:
        return self._session.scalar(
            select(Note)
            .where(Note.id == note_id)
            .options(selectinload(Note.assets))
        )

    def _get_assets(self, asset_ids: list[UUID]) -> list[Asset]:
        if not asset_ids:
            return []

        assets = list(self._session.scalars(select(Asset).where(Asset.id.in_(asset_ids))))
        assets_by_id = {asset.id: asset for asset in assets}
        missing_asset_ids = [asset_id for asset_id in asset_ids if asset_id not in assets_by_id]
        if missing_asset_ids:
            raise NotFoundError("One or more assets referenced by content_json were not found")
        return [assets_by_id[asset_id] for asset_id in asset_ids]

    def _get_or_create_tags(self, tag_names: list[str]) -> list[Tag]:
        if not tag_names:
            return []

        existing_tags = list(self._session.scalars(select(Tag).where(Tag.name.in_(tag_names))))
        tags_by_name = {tag.name: tag for tag in existing_tags}
        ordered_tags: list[Tag] = []

        for tag_name in tag_names:
            tag = tags_by_name.get(tag_name)
            if tag is None:
                tag = Tag(name=tag_name)
                self._session.add(tag)
                self._session.flush()
                tags_by_name[tag_name] = tag
            ordered_tags.append(tag)

        return ordered_tags

    def _sync_note_links(self, note: Note, links: list[ExtractedLink]) -> None:
        existing_links_by_normalized_url = {link.normalized_url: link for link in note.links}
        kept_normalized_urls: set[str] = set()

        for link in links:
            kept_normalized_urls.add(link.normalized_url)
            existing_link = existing_links_by_normalized_url.get(link.normalized_url)
            if existing_link is None:
                self._session.add(
                    NoteLink(
                        note_id=note.id,
                        url=link.url,
                        normalized_url=link.normalized_url,
                        link_type=link.link_type,
                    )
                )
                continue

            existing_link.url = link.url
            existing_link.link_type = link.link_type
            existing_link.updated_at = datetime.now(timezone.utc)

        for existing_link in note.links:
            if existing_link.normalized_url not in kept_normalized_urls:
                self._session.delete(existing_link)

    @staticmethod
    def _is_empty_draft_candidate(note: Note) -> bool:
        parsed_content = parse_note_content(note.content_json)
        return not has_meaningful_content(
            content_text_flat=parsed_content.content_text_flat,
            asset_count=len(parsed_content.asset_ids),
            link_count=len(parsed_content.links),
        )

    def _delete_note_entity(self, note: Note) -> list[str]:
        candidate_assets = list(note.assets)
        self._session.delete(note)
        self._session.flush()
        return self._delete_unused_assets(candidate_assets)

    def _delete_unused_assets(self, candidate_assets: list[Asset]) -> list[str]:
        if not candidate_assets:
            return []

        candidate_asset_ids = [asset.id for asset in candidate_assets]
        referenced_asset_ids = set(
            self._session.scalars(select(NoteAsset.asset_id).where(NoteAsset.asset_id.in_(candidate_asset_ids)))
        )

        unused_storage_keys: list[str] = []
        for asset in candidate_assets:
            if asset.id in referenced_asset_ids:
                continue
            unused_storage_keys.append(asset.storage_key)
            self._session.delete(asset)

        return unused_storage_keys

    def _create_pipeline_run(
        self,
        *,
        note_id: UUID,
        index_version: int,
        request_id: str | None,
    ) -> PipelineRunRecord:
        snapshot_asset_ids = sorted(
            self._session.scalars(select(NoteAsset.asset_id).where(NoteAsset.note_id == note_id)).all(),
            key=str,
        )
        snapshot_link_ids = sorted(
            self._session.scalars(select(NoteLink.id).where(NoteLink.note_id == note_id)).all(),
            key=str,
        )
        pipeline_run = PipelineRun(
            note_id=note_id,
            index_version=index_version,
            snapshot_asset_ids=snapshot_asset_ids,
            snapshot_link_ids=snapshot_link_ids,
            snapshot_hash=compute_snapshot_hash(
                asset_ids=snapshot_asset_ids,
                link_ids=snapshot_link_ids,
            ),
            request_id=request_id,
        )
        self._session.add(pipeline_run)
        self._session.flush()
        return PipelineRunRecord(
            id=pipeline_run.id,
            note_id=pipeline_run.note_id,
            index_version=pipeline_run.index_version,
            started_at=pipeline_run.started_at,
        )

    @staticmethod
    def _to_record(note: Note) -> NoteRecord:
        return NoteRecord(
            id=note.id,
            created_at=note.created_at,
            updated_at=note.updated_at,
            title=note.title,
            summary=note.summary,
            folder_id=note.folder_id,
            tags=[{"id": tag.id, "name": tag.name} for tag in note.tags],
            content_json=note.content_json,
            status=note.status,
            processing_error=note.processing_error,
            has_warnings=note.has_warnings,
            warnings_count=note.warnings_count,
            processing_warnings=note.processing_warnings,
            index_version=note.index_version,
        )
