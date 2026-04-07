"""DeepSeek pricing scraper — parses the API docs pricing page."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ai_price_monitor.models import PriceRecord, Provider, Tier

from .base import BaseScraper, _parse_price

logger = logging.getLogger(__name__)

_CONTEXT_WINDOW = 128_000


def _classify_tier(model_id: str) -> Tier:
    mid = model_id.lower()
    if "reasoner" in mid or "r1" in mid:
        return Tier.STANDARD
    return Tier.CHEAP  # deepseek-chat / V3 is very cheap


class DeepSeekScraper(BaseScraper):
    provider = Provider.DEEPSEEK
    source_url = "https://api-docs.deepseek.com/quick_start/pricing"

    def _parse(self, html: str) -> list[PriceRecord]:
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        if not table:
            raise ValueError("No table found on DeepSeek pricing page")

        rows = table.find_all("tr")
        if not rows:
            raise ValueError("Empty table on DeepSeek pricing page")

        # --- Header row: extract model names (skip first cell "MODEL") ---
        header_cells = rows[0].find_all(["th", "td"])
        model_ids = []
        for cell in header_cells[1:]:
            name = cell.get_text(" ", strip=True)
            if name:
                model_ids.append(name)

        if not model_ids:
            raise ValueError("Could not parse model names from DeepSeek table header")

        # --- Walk remaining rows to collect prices by label ---
        prices: dict[str, float | None] = {
            "cache_hit": None,
            "cache_miss": None,
            "output": None,
        }

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            # Flatten text from all cells
            texts = [c.get_text(" ", strip=True) for c in cells]
            combined = " ".join(texts).lower()

            # Try to extract a price from the last non-empty cell
            price_text = next(
                (t for t in reversed(texts) if re.search(r"\$[\d.]+", t)),
                None,
            )
            if price_text is None:
                continue

            try:
                price = _parse_price(price_text)
            except ValueError:
                continue

            if "cache hit" in combined or "cache_hit" in combined:
                prices["cache_hit"] = price
            elif "cache miss" in combined or "cache_miss" in combined:
                prices["cache_miss"] = price
            elif "output" in combined and "input" not in combined:
                prices["output"] = price

        # Both models currently share the same pricing
        cache_miss = prices["cache_miss"]
        cache_hit = prices["cache_hit"]
        output_p = prices["output"]

        if cache_miss is None or output_p is None:
            raise ValueError(
                f"Incomplete DeepSeek prices: cache_miss={cache_miss}, output={output_p}"
            )

        records: list[PriceRecord] = []
        for raw_name in model_ids:
            model_id = raw_name.lower().replace(" ", "-")
            if not model_id.startswith("deepseek"):
                model_id = f"deepseek-{model_id}"

            records.append(
                PriceRecord(
                    model_id=model_id,
                    model_name=raw_name,
                    provider=Provider.DEEPSEEK,
                    tier=_classify_tier(model_id),
                    input_price_per_1m=cache_miss,
                    output_price_per_1m=output_p,
                    cache_read_price=cache_hit,
                    context_window=_CONTEXT_WINDOW,
                    currency="USD",
                    notes="Cache-miss input price; cache-hit price stored in cache_read_price",
                )
            )

        if not records:
            raise ValueError("No DeepSeek pricing records parsed")
        return records
