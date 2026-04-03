"""DeepSeek pricing scraper — parses cache-miss/hit input prices."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from ai_price_monitor.models import PriceRecord, Provider, Tier

from .base import BaseScraper

logger = logging.getLogger(__name__)


def _parse_price(text: str) -> float:
    text = text.replace(",", "").strip()
    match = re.search(r"\$?([\d.]+)", text)
    if not match:
        raise ValueError(f"Cannot parse price from: {text!r}")
    return float(match.group(1))


def _classify_tier(model_id: str) -> Tier:
    mid = model_id.lower()
    if "reasoner" in mid or "r1" in mid:
        return Tier.STANDARD
    return Tier.CHEAP  # deepseek-chat / V3 is very cheap


class DeepSeekScraper(BaseScraper):
    provider = Provider.DEEPSEEK
    source_url = "https://platform.deepseek.com/pricing"

    def _parse(self, html: str) -> list[PriceRecord]:
        soup = BeautifulSoup(html, "lxml")
        records: list[PriceRecord] = []

        for table in soup.find_all("table"):
            records.extend(self._parse_table(table))

        if not records:
            records.extend(self._parse_structured_divs(soup))

        if not records:
            raise ValueError("No DeepSeek pricing records found")
        return records

    def _parse_table(self, table) -> list[PriceRecord]:
        records = []
        rows = table.find_all("tr")
        if not rows:
            return records

        headers = [th.get_text(" ", strip=True).lower() for th in rows[0].find_all(["th", "td"])]

        # Detect columns
        col_model = next((i for i, h in enumerate(headers) if "model" in h or "模型" in h), 0)
        col_input_miss = next(
            (i for i, h in enumerate(headers) if ("input" in h or "输入" in h) and "cache" not in h),
            1,
        )
        col_cache_hit = next(
            (
                i
                for i, h in enumerate(headers)
                if "cache" in h and ("hit" in h or "命中" in h or "read" in h)
            ),
            None,
        )
        col_output = next(
            (i for i, h in enumerate(headers) if "output" in h or "输出" in h), 2
        )

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            texts = [c.get_text(" ", strip=True) for c in cells]
            try:
                model_name = texts[col_model] if col_model < len(texts) else ""
                if not model_name or model_name.lower() in ("model", ""):
                    continue

                input_miss = _parse_price(texts[col_input_miss]) if col_input_miss < len(texts) else 0.0
                output_p = _parse_price(texts[col_output]) if col_output < len(texts) else 0.0
                cache_read = None
                if col_cache_hit and col_cache_hit < len(texts):
                    try:
                        cache_read = _parse_price(texts[col_cache_hit])
                    except ValueError:
                        pass

                # Detect context window
                context = None
                ctx_match = re.search(r"(\d+)\s*[Kk]", model_name)
                if ctx_match:
                    context = int(ctx_match.group(1)) * 1000

                model_id = (
                    model_name.lower()
                    .replace(" ", "-")
                    .replace("_", "-")
                )
                if not model_id.startswith("deepseek"):
                    model_id = f"deepseek-{model_id}"

                records.append(
                    PriceRecord(
                        model_id=model_id,
                        model_name=model_name,
                        provider=Provider.DEEPSEEK,
                        tier=_classify_tier(model_id),
                        input_price_per_1m=input_miss,
                        output_price_per_1m=output_p,
                        cache_read_price=cache_read,
                        context_window=context,
                        currency="USD",
                        notes="Cache-miss input price; cache-hit stored in cache_read_price",
                    )
                )
            except (ValueError, IndexError) as exc:
                logger.debug("Skipping DeepSeek row: %s", exc)
        return records

    def _parse_structured_divs(self, soup: BeautifulSoup) -> list[PriceRecord]:
        """Fallback div-based parsing for JS-heavy pages."""
        records = []
        text = soup.get_text(" ")
        # Match known model names
        pattern = re.compile(
            r"(deepseek-(?:chat|reasoner|coder|v[0-9]|r[0-9])[\w-]*)"
            r".*?\$([\d.]+).*?\$([\d.]+)",
            re.I,
        )
        seen = set()
        for m in pattern.finditer(text):
            model_id = m.group(1).lower()
            if model_id in seen:
                continue
            seen.add(model_id)
            try:
                records.append(
                    PriceRecord(
                        model_id=model_id,
                        model_name=m.group(1),
                        provider=Provider.DEEPSEEK,
                        tier=_classify_tier(model_id),
                        input_price_per_1m=float(m.group(2)),
                        output_price_per_1m=float(m.group(3)),
                        currency="USD",
                    )
                )
            except ValueError:
                continue
        return records
