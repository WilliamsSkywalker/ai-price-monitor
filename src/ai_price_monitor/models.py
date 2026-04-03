"""Pydantic data models for AI Price Monitor."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Provider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    KIMI = "kimi"
    DEEPSEEK = "deepseek"


class Tier(str, Enum):
    CHEAP = "cheap"
    STANDARD = "standard"
    PREMIUM = "premium"


class PriceRecord(BaseModel):
    """Pricing data for a single model."""

    model_id: str
    model_name: str
    provider: Provider
    tier: Tier
    input_price_per_1m: float = Field(..., description="USD per 1M input tokens")
    output_price_per_1m: float = Field(..., description="USD per 1M output tokens")
    cache_read_price: Optional[float] = Field(None, description="USD per 1M cached read tokens")
    cache_write_price: Optional[float] = Field(None, description="USD per 1M cache write tokens")
    context_window: Optional[int] = Field(None, description="Max context window in tokens")
    currency: str = Field("USD", description="Source currency before conversion")
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_prices(self) -> "PriceRecord":
        if self.input_price_per_1m < 0:
            raise ValueError(f"input_price_per_1m must be >= 0, got {self.input_price_per_1m}")
        if self.output_price_per_1m < 0:
            raise ValueError(f"output_price_per_1m must be >= 0, got {self.output_price_per_1m}")
        return self


class ProviderPricing(BaseModel):
    """All pricing data from a single provider, from one scrape."""

    provider: Provider
    source_url: str
    scraped_at: datetime
    scrape_succeeded: bool
    fallback_used: bool
    models: list[PriceRecord]


class PriceSnapshot(BaseModel):
    """Top-level object written to disk as a daily JSON snapshot."""

    snapshot_date: str = Field(..., description="YYYY-MM-DD")
    generated_at: datetime
    schema_version: str = "1.0"
    providers: list[ProviderPricing]

    def get_all_models(self) -> list[PriceRecord]:
        return [m for p in self.providers for m in p.models]

    def get_provider(self, provider: Provider) -> Optional[ProviderPricing]:
        for p in self.providers:
            if p.provider == provider:
                return p
        return None


class MonthlyUsage(BaseModel):
    """Input for the migration cost calculator."""

    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cache_read_tokens: int = Field(0, ge=0)


class CostEstimate(BaseModel):
    """Output from the migration cost calculator for a single model."""

    provider: Provider
    model_id: str
    model_name: str
    tier: Tier
    monthly_cost_usd: float
    input_cost: float
    output_cost: float
    cache_cost: float


class PriceChange(BaseModel):
    """Records a price change for a single model between two snapshots."""

    model_id: str
    model_name: str
    provider: Provider
    field: str  # "input_price_per_1m" | "output_price_per_1m" | etc.
    old_value: float
    new_value: float
    pct_change: float  # (new - old) / old * 100


class PriceDiff(BaseModel):
    """Comparison between two price snapshots."""

    old_date: str
    new_date: str
    added_models: list[PriceRecord]
    removed_models: list[PriceRecord]
    changed_models: list[PriceChange]

    @property
    def has_changes(self) -> bool:
        return bool(self.added_models or self.removed_models or self.changed_models)
