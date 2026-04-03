"""Tests for Pydantic data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_price_monitor.models import (
    CostEstimate,
    MonthlyUsage,
    PriceDiff,
    PriceRecord,
    PriceSnapshot,
    Provider,
    ProviderPricing,
    Tier,
)


def test_price_record_valid():
    record = PriceRecord(
        model_id="gpt-4o",
        model_name="GPT-4o",
        provider=Provider.OPENAI,
        tier=Tier.PREMIUM,
        input_price_per_1m=2.50,
        output_price_per_1m=10.00,
        currency="USD",
    )
    assert record.model_id == "gpt-4o"
    assert record.provider == Provider.OPENAI
    assert record.tier == Tier.PREMIUM


def test_price_record_negative_price_raises():
    with pytest.raises(ValidationError):
        PriceRecord(
            model_id="bad",
            model_name="Bad",
            provider=Provider.OPENAI,
            tier=Tier.CHEAP,
            input_price_per_1m=-1.0,
            output_price_per_1m=1.0,
            currency="USD",
        )


def test_price_record_optional_fields():
    record = PriceRecord(
        model_id="m",
        model_name="M",
        provider=Provider.DEEPSEEK,
        tier=Tier.CHEAP,
        input_price_per_1m=0.10,
        output_price_per_1m=0.50,
        currency="USD",
    )
    assert record.cache_read_price is None
    assert record.context_window is None
    assert record.notes is None


def test_monthly_usage_validation():
    u = MonthlyUsage(input_tokens=1_000_000, output_tokens=500_000)
    assert u.cache_read_tokens == 0


def test_monthly_usage_negative_raises():
    with pytest.raises(ValidationError):
        MonthlyUsage(input_tokens=-1, output_tokens=0)


def test_snapshot_get_all_models(sample_snapshot):
    models = sample_snapshot.get_all_models()
    assert len(models) == 4
    providers = {m.provider for m in models}
    assert Provider.OPENAI in providers
    assert Provider.ANTHROPIC in providers


def test_snapshot_get_provider(sample_snapshot):
    p = sample_snapshot.get_provider(Provider.OPENAI)
    assert p is not None
    assert p.provider == Provider.OPENAI

    missing = sample_snapshot.get_provider(Provider.DEEPSEEK)
    assert missing is None


def test_snapshot_serialization_roundtrip(sample_snapshot):
    json_str = sample_snapshot.model_dump_json()
    restored = PriceSnapshot.model_validate_json(json_str)
    assert restored.snapshot_date == sample_snapshot.snapshot_date
    assert len(restored.get_all_models()) == len(sample_snapshot.get_all_models())


def test_price_diff_has_changes():
    diff = PriceDiff(
        old_date="2026-04-01",
        new_date="2026-04-03",
        added_models=[],
        removed_models=[],
        changed_models=[],
    )
    assert not diff.has_changes


def test_provider_enum_values():
    assert Provider.OPENAI.value == "openai"
    assert Provider.ANTHROPIC.value == "anthropic"
    assert Provider.KIMI.value == "kimi"
    assert Provider.DEEPSEEK.value == "deepseek"


def test_tier_enum_values():
    assert Tier.CHEAP.value == "cheap"
    assert Tier.STANDARD.value == "standard"
    assert Tier.PREMIUM.value == "premium"
