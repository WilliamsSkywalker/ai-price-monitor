"""Base scraper ABC with retry logic, timeout, and static fallback support."""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ai_price_monitor import config
from ai_price_monitor.models import Provider, ProviderPricing, PriceRecord

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_STATIC_PRICES_PATH = _PROJECT_ROOT / "data" / "static_prices.json"
_STATIC_PRICES_CACHE: dict | None = None


def _load_static_prices() -> dict:
    global _STATIC_PRICES_CACHE
    if _STATIC_PRICES_CACHE is None:
        with open(_STATIC_PRICES_PATH, "r", encoding="utf-8") as f:
            _STATIC_PRICES_CACHE = json.load(f)
    return _STATIC_PRICES_CACHE


def _build_provider_pricing_from_static(provider: Provider) -> ProviderPricing:
    """Build a ProviderPricing from static_prices.json for the given provider."""
    data = _load_static_prices()
    pdata = data["providers"].get(provider.value, {})
    models = [PriceRecord(**m) for m in pdata.get("models", [])]
    return ProviderPricing(
        provider=provider,
        source_url=pdata.get("source_url", ""),
        scraped_at=datetime.now(timezone.utc),
        scrape_succeeded=False,
        fallback_used=True,
        models=models,
    )


class BaseScraper(ABC):
    """Abstract base class for all provider scrapers."""

    provider: Provider
    source_url: str

    def __init__(self):
        self.timeout = config.get("scraping", "timeout_seconds", 30)
        self.max_retries = config.get("scraping", "max_retries", 3)
        self.retry_delay = config.get("scraping", "retry_delay_seconds", 2)
        self.user_agent = config.get(
            "scraping",
            "user_agent",
            "Mozilla/5.0 (compatible; ai-price-monitor/0.1)",
        )

    def _make_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )

    def _fetch_html(self, url: str) -> str:
        """Fetch URL with retries; raises on final failure."""
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with self._make_client() as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    return resp.text
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)
        raise RuntimeError(f"All {self.max_retries} attempts failed for {url}") from last_exc

    @abstractmethod
    def _parse(self, html: str) -> list[PriceRecord]:
        """Parse HTML and return a list of PriceRecord objects."""

    def _validate(self, models: list[PriceRecord]) -> None:
        if not models:
            raise ValueError("Parser returned empty model list")
        for m in models:
            if m.input_price_per_1m < 0 or m.output_price_per_1m < 0:
                raise ValueError(f"Negative price for model {m.model_id}")

    def scrape(self) -> ProviderPricing:
        """Fetch, parse, validate → fall back to static on any error."""
        try:
            html = self._fetch_html(self.source_url)
            models = self._parse(html)
            self._validate(models)
            logger.info("%s: scraped %d models successfully", self.provider.value, len(models))
            return ProviderPricing(
                provider=self.provider,
                source_url=self.source_url,
                scraped_at=datetime.now(timezone.utc),
                scrape_succeeded=True,
                fallback_used=False,
                models=models,
            )
        except Exception as exc:
            logger.warning(
                "%s: scrape failed (%s), using static fallback",
                self.provider.value,
                exc,
            )
            return _build_provider_pricing_from_static(self.provider)

    def scrape_static(self) -> ProviderPricing:
        """Directly return static fallback (used by --force-static flag)."""
        return _build_provider_pricing_from_static(self.provider)
