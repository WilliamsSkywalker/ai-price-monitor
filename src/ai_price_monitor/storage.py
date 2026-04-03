"""JSON snapshot read/write utilities."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from ai_price_monitor import config
from ai_price_monitor.models import PriceSnapshot

logger = logging.getLogger(__name__)


def _history_dir(create: bool = False) -> Path:
    directory = config.get("general", "history_dir", "data/price_history")
    path = Path(directory)
    if not path.is_absolute():
        # Resolve relative to project root (two levels up from this file)
        root = Path(__file__).resolve().parents[2]
        path = root / path
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot_path(snapshot_date: str | date) -> Path:
    if isinstance(snapshot_date, date):
        snapshot_date = snapshot_date.strftime("%Y-%m-%d")
    return _history_dir() / f"{snapshot_date}.json"


def save_snapshot(snapshot: PriceSnapshot) -> Path:
    """Serialize and write a PriceSnapshot to disk."""
    path = _history_dir(create=True) / f"{snapshot.snapshot_date}.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(snapshot.model_dump_json(indent=2))
    logger.info("Snapshot saved: %s", path)
    return path


def load_snapshot(snapshot_date: str | date) -> PriceSnapshot | None:
    """Load a PriceSnapshot from disk; returns None if not found."""
    path = snapshot_path(snapshot_date)
    try:
        return PriceSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def load_latest_snapshot() -> PriceSnapshot | None:
    """Return the most recently saved snapshot, or None."""
    snapshots = sorted(_history_dir().glob("????-??-??.json"), reverse=True)
    if not snapshots:
        return None
    return PriceSnapshot.model_validate_json(snapshots[0].read_text(encoding="utf-8"))


def list_snapshots() -> list[str]:
    """Return sorted list of available snapshot dates (YYYY-MM-DD) desc."""
    return sorted(
        [p.stem for p in _history_dir().glob("????-??-??.json")],
        reverse=True,
    )


def make_snapshot(providers_data, today: date | None = None) -> PriceSnapshot:
    """Build a PriceSnapshot from a list of ProviderPricing objects."""
    today = today or date.today()
    return PriceSnapshot(
        snapshot_date=today.strftime("%Y-%m-%d"),
        generated_at=datetime.now(timezone.utc),
        providers=providers_data,
    )
