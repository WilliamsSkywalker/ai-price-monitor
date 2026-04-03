"""Scraper registry and run_all() orchestration."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ai_price_monitor.models import Provider, ProviderPricing

from .anthropic import AnthropicScraper
from .base import BaseScraper
from .deepseek import DeepSeekScraper
from .kimi import KimiScraper
from .openai import OpenAIScraper

logger = logging.getLogger(__name__)

REGISTRY: dict[Provider, type[BaseScraper]] = {
    Provider.OPENAI: OpenAIScraper,
    Provider.ANTHROPIC: AnthropicScraper,
    Provider.KIMI: KimiScraper,
    Provider.DEEPSEEK: DeepSeekScraper,
}


def run_all(force_static: bool = False) -> list[ProviderPricing]:
    """Scrape all providers in parallel; return list of ProviderPricing."""
    results: list[ProviderPricing] = []

    def _scrape_one(provider: Provider, cls: type[BaseScraper]) -> ProviderPricing:
        scraper = cls()
        if force_static:
            return scraper.scrape_static()
        return scraper.scrape()

    with ThreadPoolExecutor(max_workers=len(REGISTRY)) as pool:
        futures = {
            pool.submit(_scrape_one, provider, cls): provider
            for provider, cls in REGISTRY.items()
        }
        for future in as_completed(futures):
            provider = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                logger.error("Unexpected error scraping %s: %s", provider, exc)

    # Sort by provider enum value for deterministic output
    results.sort(key=lambda r: r.provider.value)
    return results
