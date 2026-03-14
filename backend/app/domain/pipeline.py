from __future__ import annotations

from hashlib import sha256
from uuid import UUID


def compute_snapshot_hash(*, asset_ids: list[UUID], link_ids: list[UUID]) -> str:
    sorted_asset_ids = sorted(str(asset_id) for asset_id in asset_ids)
    sorted_link_ids = sorted(str(link_id) for link_id in link_ids)
    snapshot_payload = "|".join([*sorted_asset_ids, "--", *sorted_link_ids])
    return sha256(snapshot_payload.encode("utf-8")).hexdigest()
