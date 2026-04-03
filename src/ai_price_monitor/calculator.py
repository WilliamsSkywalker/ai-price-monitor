"""Migration cost calculator — pure functions, no I/O."""

from __future__ import annotations

from ai_price_monitor.models import CostEstimate, MonthlyUsage, PriceRecord, PriceSnapshot


def estimate_cost(model: PriceRecord, usage: MonthlyUsage) -> CostEstimate:
    """Compute monthly cost estimate for a single model given usage."""
    m_input = usage.input_tokens / 1_000_000
    m_output = usage.output_tokens / 1_000_000
    m_cache = usage.cache_read_tokens / 1_000_000

    input_cost = m_input * model.input_price_per_1m
    output_cost = m_output * model.output_price_per_1m
    cache_cost = m_cache * (model.cache_read_price or 0.0)
    total = input_cost + output_cost + cache_cost

    return CostEstimate(
        provider=model.provider,
        model_id=model.model_id,
        model_name=model.model_name,
        tier=model.tier,
        monthly_cost_usd=round(total, 4),
        input_cost=round(input_cost, 4),
        output_cost=round(output_cost, 4),
        cache_cost=round(cache_cost, 4),
    )


def estimate_all(snapshot: PriceSnapshot, usage: MonthlyUsage) -> list[CostEstimate]:
    """Compute cost estimates for all models in a snapshot, sorted by cost."""
    estimates = [estimate_cost(m, usage) for m in snapshot.get_all_models()]
    return sorted(estimates, key=lambda e: e.monthly_cost_usd)


def migration_savings(
    from_model: PriceRecord,
    to_model: PriceRecord,
    usage: MonthlyUsage,
) -> dict:
    """Calculate potential savings of switching from one model to another."""
    from_estimate = estimate_cost(from_model, usage)
    to_estimate = estimate_cost(to_model, usage)
    savings = from_estimate.monthly_cost_usd - to_estimate.monthly_cost_usd
    pct = (savings / from_estimate.monthly_cost_usd * 100) if from_estimate.monthly_cost_usd else 0
    return {
        "from_model": from_model.model_id,
        "to_model": to_model.model_id,
        "from_cost_usd": from_estimate.monthly_cost_usd,
        "to_cost_usd": to_estimate.monthly_cost_usd,
        "monthly_savings_usd": round(savings, 4),
        "savings_pct": round(pct, 2),
    }
