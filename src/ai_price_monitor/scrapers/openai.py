"""OpenAI pricing scraper — parses __NEXT_DATA__ JSON from the pricing page."""

from __future__ import annotations

import json
import logging
import re

from ai_price_monitor.models import PriceRecord, Provider, Tier

from .base import BaseScraper

logger = logging.getLogger(__name__)

# Tier classification by model_id keyword
_TIER_MAP: list[tuple[list[str], Tier]] = [
    (["o1", "o3", "o4", "gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-4"], Tier.PREMIUM),
    (["o3-mini", "o1-mini", "gpt-4.1-mini", "gpt-4o-mini", "gpt-3.5"], Tier.CHEAP),
]


def _classify_tier(model_id: str) -> Tier:
    mid = model_id.lower()
    for keywords, tier in _TIER_MAP:
        for kw in keywords:
            if kw in mid:
                return tier
    return Tier.STANDARD


def _dollars_to_float(value) -> float:
    """Convert price value to float (handles string '$X.XX' or numeric)."""
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value).replace("$", "").replace(",", "").strip())


class OpenAIScraper(BaseScraper):
    provider = Provider.OPENAI
    source_url = "https://openai.com/api/pricing"

    def _parse(self, html: str) -> list[PriceRecord]:
        # Strategy 1: Extract __NEXT_DATA__ JSON
        match = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if match:
            try:
                return self._parse_next_data(json.loads(match.group(1)))
            except Exception as exc:
                logger.debug("__NEXT_DATA__ parse failed: %s", exc)

        # Strategy 2: Look for embedded JSON blobs with pricing arrays
        return self._parse_html_tables(html)

    def _parse_next_data(self, data: dict) -> list[PriceRecord]:
        """Recursively find pricing arrays inside __NEXT_DATA__."""
        records: list[PriceRecord] = []
        self._walk_next_data(data, records)
        if not records:
            raise ValueError("No pricing records found in __NEXT_DATA__")
        return records

    def _walk_next_data(self, obj, records: list[PriceRecord]) -> None:
        """Walk the NEXT_DATA tree looking for model pricing objects."""
        if isinstance(obj, dict):
            # Look for objects that look like a pricing row
            if "inputPrice" in obj or "input_price" in obj or "inputTokensPrice" in obj:
                record = self._extract_record_from_dict(obj)
                if record:
                    records.append(record)
                    return
            for v in obj.values():
                self._walk_next_data(v, records)
        elif isinstance(obj, list):
            for item in obj:
                self._walk_next_data(item, records)

    def _extract_record_from_dict(self, obj: dict) -> PriceRecord | None:
        try:
            model_id = (
                obj.get("slug")
                or obj.get("model_id")
                or obj.get("id")
                or obj.get("name", "")
            )
            model_name = obj.get("name") or obj.get("displayName") or model_id

            input_price = _dollars_to_float(
                obj.get("inputPrice")
                or obj.get("input_price")
                or obj.get("inputTokensPrice")
                or 0
            )
            output_price = _dollars_to_float(
                obj.get("outputPrice")
                or obj.get("output_price")
                or obj.get("outputTokensPrice")
                or 0
            )
            cache_read = obj.get("cachedInputPrice") or obj.get("cache_read_price")
            context = obj.get("contextWindow") or obj.get("context_window")

            if not model_id or (input_price == 0 and output_price == 0):
                return None

            return PriceRecord(
                model_id=model_id,
                model_name=str(model_name),
                provider=Provider.OPENAI,
                tier=_classify_tier(str(model_id)),
                input_price_per_1m=input_price,
                output_price_per_1m=output_price,
                cache_read_price=_dollars_to_float(cache_read) if cache_read else None,
                context_window=int(context) if context else None,
                currency="USD",
            )
        except Exception as exc:
            logger.debug("Failed to extract record from dict %s: %s", obj, exc)
            return None

    def _parse_html_tables(self, html: str) -> list[PriceRecord]:
        """Fallback: parse HTML tables — raises if nothing found."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        records: list[PriceRecord] = []

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            for row in rows[1:]:  # skip header
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) < 3:
                    continue
                try:
                    model_id = cells[0].lower().replace(" ", "-")
                    input_p = _dollars_to_float(cells[1].split("/")[0])
                    output_p = _dollars_to_float(cells[2].split("/")[0])
                    records.append(
                        PriceRecord(
                            model_id=model_id,
                            model_name=cells[0],
                            provider=Provider.OPENAI,
                            tier=_classify_tier(model_id),
                            input_price_per_1m=input_p,
                            output_price_per_1m=output_p,
                            currency="USD",
                        )
                    )
                except (ValueError, IndexError):
                    continue

        if not records:
            raise ValueError("No pricing records found in OpenAI HTML tables")
        return records
