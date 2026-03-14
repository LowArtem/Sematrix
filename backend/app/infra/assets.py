from __future__ import annotations

from pathlib import Path


CONTAINER_ASSETS_ROOT = Path("/data/assets")


def get_assets_root() -> Path:
    if CONTAINER_ASSETS_ROOT.exists():
        return CONTAINER_ASSETS_ROOT
    return Path(__file__).resolve().parents[3] / "data" / "assets"


def get_asset_path(storage_key: str) -> Path:
    return get_assets_root() / storage_key
