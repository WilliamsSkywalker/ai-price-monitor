"""Anthropic pricing scraper — parses SSR HTML tables from the pricing page."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ai_price_monitor.models import PriceRecord, Provider, Tier

from .base import BaseScraper, _parse_price, _slug

logger = logging.getLogger(__name__)


def _classify_tier(model_name: str) -> Tier:
    name = model_name.lower()
    if "opus" in name:
        return Tier.PREMIUM
    if "haiku" in name:
        return Tier.CHEAP
    return Tier.STANDARD  # Sonnet


class AnthropicScraper(BaseScraper):
    provider = Provider.ANTHROPIC
    source_url = "https://www.anthropic.com/pricing"

    def _parse(self, html: str) -> list[PriceRecord]:
        soup = BeautifulSoup(html, "lxml")
        records: list[PriceRecord] = []

        # Find all tables or pricing card sections
        for table in soup.find_all("table"):
            records.extend(self._parse_table(table))

        # Fallback: look for pricing rows in structured divs
        if not records:
            records.extend(self._parse_divs(soup))

        if not records:
            raise ValueError("No Anthropic pricing records found in page")
        return records

    def _parse_table(self, table) -> list[PriceRecord]:
        """Parse a standard HTML <table> for model pricing."""
        records = []
        rows = table.find_all("tr")
        headers = []
        if rows:
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        # Detect column positions
        col_model = next((i for i, h in enumerate(headers) if "model" in h), 0)
        col_input = next((i for i, h in enumerate(headers) if "input" in h), 1)
        col_output = next((i for i, h in enumerate(headers) if "output" in h), 2)
        col_context = next((i for i, h in enumerate(headers) if "context" in h), None)

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue
            texts = [c.get_text(" ", strip=True) for c in cells]
            try:
                model_name = texts[col_model]
                if not model_name or model_name.lower() in ("model", ""):
                    continue
                input_p = _parse_price(texts[col_input])
                output_p = _parse_price(texts[col_output])
                context = None
                if col_context and col_context < len(texts):
                    ctx_text = texts[col_context].replace(",", "").replace("K", "000")
                    ctx_match = re.search(r"(\d+)", ctx_text)
                    if ctx_match:
                        context = int(ctx_match.group(1))

                # Detect cache pricing columns
                cache_read = None
                for i, h in enumerate(headers):
                    if "cache" in h and "read" in h and i < len(texts):
                        try:
                            cache_read = _parse_price(texts[i])
                        except ValueError:
                            pass

                model_id = _slug(model_name)
                records.append(
                    PriceRecord(
                        model_id=model_id,
                        model_name=model_name,
                        provider=Provider.ANTHROPIC,
                        tier=_classify_tier(model_name),
                        input_price_per_1m=input_p,
                        output_price_per_1m=output_p,
                        cache_read_price=cache_read,
                        context_window=context,
                        currency="USD",
                    )
                )
            except (ValueError, IndexError) as exc:
                logger.debug("Skipping Anthropic row: %s", exc)
        return records

    def _parse_divs(self, soup: BeautifulSoup) -> list[PriceRecord]:
        """Heuristic: find pricing data in structured div/card layouts."""
        records = []
        # Look for elements containing model names
        for elem in soup.find_all(string=re.compile(r"claude", re.I)):
            parent = elem.find_parent()
            if not parent:
                continue
            container = parent.find_parent()
            if not container:
                continue
            text = container.get_text(" ", strip=True)
            prices = re.findall(r"\$([\d.]+)", text)
            if len(prices) >= 2:
                model_name = str(elem).strip()
                try:
                    records.append(
                        PriceRecord(
                            model_id=_slug(model_name),
                            model_name=model_name,
                            provider=Provider.ANTHROPIC,
                            tier=_classify_tier(model_name),
                            input_price_per_1m=float(prices[0]),
                            output_price_per_1m=float(prices[1]),
                            currency="USD",
                        )
                    )
                except ValueError:
                    continue
        return records
