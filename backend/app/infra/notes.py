from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.domain.errors import NotFoundError
from app.domain.note_lifecycle import build_draft_reset_state
from app.domain.note_content import ExtractedLink
from app.infra.assets import get_asset_path
from app.infra.models import Asset, Folder, Note, NoteAsset, NoteLink, NoteTag, Tag


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
class SaveNoteRecord:
    note: NoteRecord
    pipeline_started: bool


class NoteRepository(Protocol):
    def create_note(self) -> NoteRecord: ...

    def get_note(self, note_id: UUID) -> NoteRecord | None: ...

    def delete_note(self, note_id: UUID) -> None: ...

    def reindex_note(self, note_id: UUID) -> NoteRecord: ...

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

        candidate_assets = list(note.assets)
        self._session.delete(note)
        self._session.flush()

        asset_storage_keys_to_delete = self._delete_unused_assets(candidate_assets)
        self._session.commit()

        for storage_key in asset_storage_keys_to_delete:
            get_asset_path(storage_key).unlink(missing_ok=True)

    def reindex_note(self, note_id: UUID) -> NoteRecord:
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
        self._session.commit()

        reindexed_note = self._get_note_with_relations(note_id)
        if reindexed_note is None:
            raise NotFoundError("Note not found")

        return self._to_record(reindexed_note)

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

        if should_start_processing:
            note.index_version += 1
            note.status = "Processing"
            note.processing_error = None
            note.has_warnings = False
            note.warnings_count = 0
            note.processing_warnings = []
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

        return SaveNoteRecord(note=self._to_record(saved_note), pipeline_started=should_start_processing)

    def list_notes(
        self,
        *,
        text_query: str,
        tag_names: list[str],
        folder_id: UUID | None,
        limit: int,
        offset: int,
    ) -> NoteListRecord:
        note_ids_query = select(Note.id)

        if folder_id is not None:
            note_ids_query = note_ids_query.where(Note.folder_id == folder_id)

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

        if tag_names:
            note_ids_query = (
                note_ids_query.join(NoteTag, NoteTag.note_id == Note.id)
                .join(Tag, Tag.id == NoteTag.tag_id)
                .where(Tag.name.in_(tag_names))
                .group_by(Note.id)
                .having(func.count(func.distinct(Tag.name)) == len(tag_names))
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

    def _get_note_with_relations(self, note_id: UUID) -> Note | None:
        return self._session.scalar(
            select(Note)
            .where(Note.id == note_id)
            .options(selectinload(Note.tags), selectinload(Note.assets), selectinload(Note.links))
        )

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
