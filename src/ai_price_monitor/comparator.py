"""Price comparison: diff two snapshots and group by tier."""

from __future__ import annotations

from ai_price_monitor.models import (
    PriceChange,
    PriceDiff,
    PriceRecord,
    PriceSnapshot,
    Tier,
)

_PRICE_FIELDS = ["input_price_per_1m", "output_price_per_1m", "cache_read_price"]


def diff_snapshots(old: PriceSnapshot, new: PriceSnapshot) -> PriceDiff:
    """Compare two snapshots and return a PriceDiff."""
    old_models = {m.model_id: m for m in old.get_all_models()}
    new_models = {m.model_id: m for m in new.get_all_models()}

    added = [m for mid, m in new_models.items() if mid not in old_models]
    removed = [m for mid, m in old_models.items() if mid not in new_models]

    changes: list[PriceChange] = []
    for mid, new_m in new_models.items():
        if mid not in old_models:
            continue
        old_m = old_models[mid]
        for field in _PRICE_FIELDS:
            old_val = getattr(old_m, field)
            new_val = getattr(new_m, field)
            if old_val is None and new_val is None:
                continue
            old_val = old_val or 0.0
            new_val = new_val or 0.0
            if abs(old_val - new_val) < 1e-9:
                continue
            pct = ((new_val - old_val) / old_val * 100) if old_val else float("inf")
            changes.append(
                PriceChange(
                    model_id=mid,
                    model_name=new_m.model_name,
                    provider=new_m.provider,
                    field=field,
                    old_value=old_val,
                    new_value=new_val,
                    pct_change=round(pct, 2),
                )
            )

    return PriceDiff(
        old_date=old.snapshot_date,
        new_date=new.snapshot_date,
        added_models=added,
        removed_models=removed,
        changed_models=changes,
    )


def group_by_tier(models: list[PriceRecord]) -> dict[Tier, list[PriceRecord]]:
    """Group model list by tier (cheap / standard / premium)."""
    result: dict[Tier, list[PriceRecord]] = {t: [] for t in Tier}
    for m in models:
        result[m.tier].append(m)
    return result


def sort_models(
    models: list[PriceRecord],
    sort_by: str = "output_price_per_1m",
    ascending: bool = True,
) -> list[PriceRecord]:
    """Return models sorted by the given field."""
    valid_fields = {"input_price_per_1m", "output_price_per_1m", "provider", "model_name", "tier"}
    if sort_by not in valid_fields:
        sort_by = "output_price_per_1m"
    return sorted(models, key=lambda m: getattr(m, sort_by) or 0, reverse=not ascending)


def filter_by_tier(models: list[PriceRecord], tier: Tier | None) -> list[PriceRecord]:
    if tier is None:
        return models
    return [m for m in models if m.tier == tier]


def filter_by_providers(models: list[PriceRecord], providers: list[str] | None) -> list[PriceRecord]:
    if not providers:
        return models
    provider_set = set(providers)
    return [m for m in models if m.provider.value in provider_set]
