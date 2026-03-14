from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_APP = REPO_ROOT / "backend" / "app"


def test_celery_beat_schedules_draft_cleanup_task() -> None:
    celery_app_source = (BACKEND_APP / "workers" / "celery_app.py").read_text(encoding="utf-8")

    assert 'from datetime import timedelta' in celery_app_source
    assert '"draft-cleanup": {' in celery_app_source
    assert '"task": "sematrix.cleanup_drafts"' in celery_app_source
    assert '"schedule": timedelta(hours=settings.draft_ttl_hours)' in celery_app_source


def test_worker_exposes_cleanup_task_and_logs_counts() -> None:
    worker_source = (BACKEND_APP / "workers" / "tasks.py").read_text(encoding="utf-8")
    logging_source = (BACKEND_APP / "core" / "logging.py").read_text(encoding="utf-8")

    assert '@celery_app.task(bind=True, name="sematrix.cleanup_drafts")' in worker_source
    assert 'service = DraftCleanupService(note_repository=SqlAlchemyNoteRepository(session=session))' in worker_source
    assert 'result = service.cleanup_expired_empty_drafts(ttl_hours=settings.draft_ttl_hours)' in worker_source
    assert '"draft_cleanup_finished"' in worker_source
    assert '"candidate_count": result.candidate_count' in worker_source
    assert '"deleted_draft_count": result.deleted_draft_count' in worker_source
    assert '"deleted_asset_count": result.deleted_asset_count' in worker_source
    assert '"deletion_errors": result.deletion_errors' in worker_source
    assert '"candidate_count"' in logging_source
    assert '"deleted_draft_count"' in logging_source
    assert '"deleted_asset_count"' in logging_source
    assert '"deletion_errors"' in logging_source


def test_note_repository_filters_empty_expired_drafts_and_deletes_orphan_assets() -> None:
    domain_source = (BACKEND_APP / "domain" / "notes.py").read_text(encoding="utf-8")
    infra_source = (BACKEND_APP / "infra" / "notes.py").read_text(encoding="utf-8")

    assert 'class DraftCleanupService:' in domain_source
    assert 'def cleanup_expired_empty_drafts(self, *, ttl_hours: int) -> DraftCleanupResult:' in domain_source
    assert 'self._note_repository.cleanup_expired_empty_drafts(ttl_hours=ttl_hours)' in domain_source
    assert 'cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)' in infra_source
    assert '.where(Note.status == "Draft", Note.updated_at <= cutoff)' in infra_source
    assert 'if self._is_empty_draft_candidate(note)' in infra_source
    assert 'parsed_content = parse_note_content(note.content_json)' in infra_source
    assert 'return not has_meaningful_content(' in infra_source
    assert 'asset_count=len(parsed_content.asset_ids)' in infra_source
    assert 'link_count=len(parsed_content.links)' in infra_source
    assert 'asset_storage_keys_to_delete = self._delete_note_entity(note)' in infra_source
    assert 'deleted_asset_count += len(asset_storage_keys_to_delete)' in infra_source
    assert 'deletion_errors.append(f"{note_id}: {exc}")' in infra_source
