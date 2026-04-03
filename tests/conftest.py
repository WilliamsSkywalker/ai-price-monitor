"""Pytest fixtures shared across tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_price_monitor.models import (
    MonthlyUsage,
    PriceRecord,
    PriceSnapshot,
    Provider,
    ProviderPricing,
    Tier,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_record(
    model_id: str,
    provider: Provider,
    tier: Tier,
    input_price: float,
    output_price: float,
    cache_read: float | None = None,
    context: int | None = None,
) -> PriceRecord:
    return PriceRecord(
        model_id=model_id,
        model_name=model_id.replace("-", " ").title(),
        provider=provider,
        tier=tier,
        input_price_per_1m=input_price,
        output_price_per_1m=output_price,
        cache_read_price=cache_read,
        context_window=context,
        currency="USD",
    )


@pytest.fixture
def sample_openai_models():
    return [
        _make_record("gpt-4o", Provider.OPENAI, Tier.PREMIUM, 2.50, 10.00, 1.25, 128000),
        _make_record("gpt-4o-mini", Provider.OPENAI, Tier.CHEAP, 0.15, 0.60, 0.075, 128000),
    ]


@pytest.fixture
def sample_anthropic_models():
    return [
        _make_record("claude-sonnet-4-5", Provider.ANTHROPIC, Tier.STANDARD, 3.00, 15.00, 0.30, 200000),
        _make_record("claude-haiku-3-5", Provider.ANTHROPIC, Tier.CHEAP, 0.80, 4.00, 0.08, 200000),
    ]


@pytest.fixture
def sample_snapshot(sample_openai_models, sample_anthropic_models):
    now = datetime.now(timezone.utc)
    return PriceSnapshot(
        snapshot_date="2026-04-03",
        generated_at=now,
        providers=[
            ProviderPricing(
                provider=Provider.OPENAI,
                source_url="https://openai.com/api/pricing",
                scraped_at=now,
                scrape_succeeded=True,
                fallback_used=False,
                models=sample_openai_models,
            ),
            ProviderPricing(
                provider=Provider.ANTHROPIC,
                source_url="https://www.anthropic.com/pricing",
                scraped_at=now,
                scrape_succeeded=True,
                fallback_used=False,
                models=sample_anthropic_models,
            ),
        ],
    )


@pytest.fixture
def sample_usage():
    return MonthlyUsage(
        input_tokens=10_000_000,
        output_tokens=3_000_000,
        cache_read_tokens=0,
    )
