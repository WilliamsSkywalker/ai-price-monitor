"""Kimi (Moonshot) pricing scraper — parses CNY prices and converts to USD."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ai_price_monitor import config
from ai_price_monitor.models import PriceRecord, Provider, Tier

from .base import BaseScraper

logger = logging.getLogger(__name__)


def _cny_to_usd(cny: float) -> float:
    rate = config.get("general", "usd_to_cny", 7.25)
    return round(cny / rate, 6)


def _parse_price(text: str) -> float:
    """Extract numeric price from strings like '¥1.2/百万tokens' or '1.2'."""
    text = text.replace(",", "").strip()
    match = re.search(r"[\d.]+", text)
    if not match:
        raise ValueError(f"Cannot parse price from: {text!r}")
    return float(match.group())


def _classify_tier(model_id: str) -> Tier:
    if "8k" in model_id.lower():
        return Tier.CHEAP
    if "32k" in model_id.lower():
        return Tier.STANDARD
    return Tier.PREMIUM  # 128k and above


class KimiScraper(BaseScraper):
    provider = Provider.KIMI
    source_url = "https://platform.moonshot.cn/docs/pricing/chat"

    def _parse(self, html: str) -> list[PriceRecord]:
        soup = BeautifulSoup(html, "lxml")
        records: list[PriceRecord] = []

        for table in soup.find_all("table"):
            records.extend(self._parse_table(table))

        if not records:
            records.extend(self._parse_text(soup))

        if not records:
            raise ValueError("No Kimi pricing records found")
        return records

    def _parse_table(self, table) -> list[PriceRecord]:
        records = []
        rows = table.find_all("tr")
        if not rows:
            return records

        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
        col_model = next((i for i, h in enumerate(headers) if "模型" in h or "model" in h), 0)
        col_input = next(
            (i for i, h in enumerate(headers) if "输入" in h or "input" in h), 1
        )
        col_output = next(
            (i for i, h in enumerate(headers) if "输出" in h or "output" in h), 2
        )

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            texts = [c.get_text(" ", strip=True) for c in cells]
            try:
                model_name = texts[col_model]
                if not model_name:
                    continue
                input_cny = _parse_price(texts[col_input])
                output_cny = (
                    _parse_price(texts[col_output]) if col_output < len(texts) else input_cny
                )

                # Detect context window from model name
                context = None
                ctx_match = re.search(r"(\d+)k", model_name, re.I)
                if ctx_match:
                    context = int(ctx_match.group(1)) * 1000

                model_id = model_name.lower().replace(" ", "-").replace("_", "-")
                records.append(
                    PriceRecord(
                        model_id=model_id,
                        model_name=model_name,
                        provider=Provider.KIMI,
                        tier=_classify_tier(model_name),
                        input_price_per_1m=_cny_to_usd(input_cny),
                        output_price_per_1m=_cny_to_usd(output_cny),
                        context_window=context,
                        currency="CNY",
                        notes=f"CNY {input_cny}/{output_cny} per 1M tokens",
                    )
                )
            except (ValueError, IndexError) as exc:
                logger.debug("Skipping Kimi row: %s", exc)
        return records

    def _parse_text(self, soup: BeautifulSoup) -> list[PriceRecord]:
        """Fallback: regex on page text for CNY price patterns."""
        records = []
        text = soup.get_text(" ")
        # Pattern: 'moonshot-v1-8k ... ¥X.X'
        pattern = re.compile(
            r"(moonshot-v1-(?:8k|32k|128k)|kimi-[a-z0-9-]+)"
            r".*?"
            r"[¥￥]?([\d.]+)\s*(?:/百万|/million|per\s*1m)?",
            re.I,
        )
        seen = set()
        for match in pattern.finditer(text):
            model_id = match.group(1).lower()
            if model_id in seen:
                continue
            seen.add(model_id)
            try:
                price_cny = float(match.group(2))
                records.append(
                    PriceRecord(
                        model_id=model_id,
                        model_name=match.group(1),
                        provider=Provider.KIMI,
                        tier=_classify_tier(model_id),
                        input_price_per_1m=_cny_to_usd(price_cny),
                        output_price_per_1m=_cny_to_usd(price_cny),
                        currency="CNY",
                    )
                )
            except ValueError:
                continue
        return records
