"""Tests for the migration cost calculator."""

from __future__ import annotations

import pytest

from ai_price_monitor.calculator import estimate_all, estimate_cost, migration_savings
from ai_price_monitor.models import MonthlyUsage, Provider, Tier


def test_estimate_cost_basic(sample_openai_models, sample_usage):
    """GPT-4o: $2.50/1M in + $10.00/1M out, 10M+3M tokens."""
    gpt4o = next(m for m in sample_openai_models if m.model_id == "gpt-4o")
    est = estimate_cost(gpt4o, sample_usage)
    # 10M * $2.50 = $25.00 input, 3M * $10.00 = $30.00 output
    assert est.input_cost == pytest.approx(25.00, abs=0.01)
    assert est.output_cost == pytest.approx(30.00, abs=0.01)
    assert est.monthly_cost_usd == pytest.approx(55.00, abs=0.01)
    assert est.cache_cost == 0.0
    assert est.provider == Provider.OPENAI
    assert est.tier == Tier.PREMIUM


def test_estimate_cost_with_cache(sample_openai_models):
    """GPT-4o with cache read tokens."""
    gpt4o = next(m for m in sample_openai_models if m.model_id == "gpt-4o")
    usage = MonthlyUsage(input_tokens=1_000_000, output_tokens=0, cache_read_tokens=2_000_000)
    est = estimate_cost(gpt4o, usage)
    # input: 1M * $2.50 = $2.50, cache: 2M * $1.25 = $2.50
    assert est.input_cost == pytest.approx(2.50, abs=0.01)
    assert est.cache_cost == pytest.approx(2.50, abs=0.01)
    assert est.monthly_cost_usd == pytest.approx(5.00, abs=0.01)


def test_estimate_cost_zero_usage():
    from tests.conftest import _make_record
    model = _make_record("test", Provider.DEEPSEEK, Tier.CHEAP, 0.27, 1.10)
    usage = MonthlyUsage(input_tokens=0, output_tokens=0)
    est = estimate_cost(model, usage)
    assert est.monthly_cost_usd == 0.0


def test_estimate_all_sorted(sample_snapshot, sample_usage):
    estimates = estimate_all(sample_snapshot, sample_usage)
    costs = [e.monthly_cost_usd for e in estimates]
    assert costs == sorted(costs), "Estimates should be sorted cheapest first"


def test_estimate_all_coverage(sample_snapshot, sample_usage):
    estimates = estimate_all(sample_snapshot, sample_usage)
    model_ids = {e.model_id for e in estimates}
    snapshot_ids = {m.model_id for m in sample_snapshot.get_all_models()}
    assert model_ids == snapshot_ids


def test_migration_savings(sample_openai_models, sample_usage):
    gpt4o = next(m for m in sample_openai_models if m.model_id == "gpt-4o")
    mini = next(m for m in sample_openai_models if m.model_id == "gpt-4o-mini")
    result = migration_savings(gpt4o, mini, sample_usage)
    assert result["monthly_savings_usd"] > 0
    assert result["savings_pct"] > 0
    assert result["from_model"] == "gpt-4o"
    assert result["to_model"] == "gpt-4o-mini"


def test_migration_savings_negative_when_more_expensive(sample_openai_models, sample_usage):
    gpt4o = next(m for m in sample_openai_models if m.model_id == "gpt-4o")
    mini = next(m for m in sample_openai_models if m.model_id == "gpt-4o-mini")
    result = migration_savings(mini, gpt4o, sample_usage)
    assert result["monthly_savings_usd"] < 0  # switching to more expensive model
