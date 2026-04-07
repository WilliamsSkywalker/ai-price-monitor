"""OpenAI pricing scraper.

Strategy
--------
1. Try httpx (fast but usually blocked by Cloudflare).
2. If that fails, launch Playwright, wait for the page to render, and extract
   prices from all visible model cards via injected JavaScript.
3. If Playwright is unavailable or fails, fall back to bundled static prices.
"""

from __future__ import annotations

import logging
import re

from ai_price_monitor.models import PriceRecord, Provider, Tier

from .base import BaseScraper, _BROWSER_UA, _slug

logger = logging.getLogger(__name__)

# Tier classification by model_id keyword.
# CHEAP is checked first so "-mini" / "-nano" suffixes take priority over
# the bare family name (e.g. "gpt-5.4-mini" → CHEAP, not PREMIUM).
_TIER_MAP: list[tuple[list[str], Tier]] = [
    (["o3-mini", "o4-mini", "o1-mini", "gpt-4.1-mini", "gpt-4o-mini", "gpt-3.5", "-mini", "-nano"], Tier.CHEAP),
    (["o1", "o3", "o4", "gpt-4o", "gpt-4.1", "gpt-4-turbo", "gpt-4", "gpt-5"], Tier.PREMIUM),
]


def _classify_tier(model_id: str) -> Tier:
    mid = model_id.lower()
    for keywords, tier in _TIER_MAP:
        for kw in keywords:
            if kw in mid:
                return tier
    return Tier.STANDARD


def _parse_price_text(text: str) -> float:
    """Extract dollar amount from strings like 'Input: $2.50 / 1M tokens'."""
    m = re.search(r"\$([\d,]+(?:\.\d+)?)", text)
    if not m:
        raise ValueError(f"No price in {text!r}")
    return float(m.group(1).replace(",", ""))


# ---------------------------------------------------------------------------
# JS snippet run inside the Playwright page to extract card data.
# Returns a list of {name, input, cached, output} dicts.
# ---------------------------------------------------------------------------
_EXTRACT_JS = """
() => {
    const priceRe = /\\$([\\d,]+(?:\\.\\d+)?)/;

    // True if the element's first non-empty text node starts with a price label.
    // Handles spans like <span>Input: <br/> $2.50 / 1M tokens</span> where the
    // <br> child means el.children.length > 0 (not a leaf node).
    function isPriceEl(el) {
        for (const n of el.childNodes) {
            if (n.nodeType !== 3) continue;           // TEXT_NODE = 3
            const t = n.textContent.trim();
            if (!t) continue;
            return /^(Input|Output|Cached input):/i.test(t);
        }
        return false;
    }

    function getPrice(el) {
        const t = el.textContent.replace(/\\s+/g, ' ');
        const m = t.match(priceRe);
        return m ? parseFloat(m[1].replace(',', '')) : null;
    }

    function firstLabel(el) {
        for (const n of el.childNodes) {
            if (n.nodeType !== 3) continue;
            const t = n.textContent.trim();
            if (t) return t;
        }
        return '';
    }

    function getCardPrices(root) {
        const info = {};
        root.querySelectorAll('*').forEach(el => {
            if (!isPriceEl(el)) return;
            const price = getPrice(el);
            if (price === null) return;
            const lbl = firstLabel(el);
            if (/^Input:/i.test(lbl) && !/Cached/i.test(lbl)) info.input  = price;
            else if (/^Cached input:/i.test(lbl))              info.cached = price;
            else if (/^Output:/i.test(lbl))                    info.output = price;
        });
        return info;
    }

    const results = [];
    const seen   = new WeakSet();

    document.querySelectorAll('*').forEach(el => {
        if (!isPriceEl(el)) return;

        // Climb until we find a container with >=2 price elements AND a real model heading
        // (skip inner containers whose only heading is the generic "Price" label)
        let card = el.parentElement;
        for (let i = 0; i < 15 && card && card !== document.body; i++) {
            const cnt = Array.from(card.querySelectorAll('*')).filter(isPriceEl).length;
            if (cnt >= 2) {
                const h = card.querySelector('h1,h2,h3,h4,h5,h6,[role="heading"]');
                const hText = h ? h.textContent.trim() : '';
                if (hText && hText.toLowerCase() !== 'price') break;
            }
            card = card.parentElement;
        }
        if (!card || seen.has(card)) return;
        seen.add(card);

        const prices = getCardPrices(card);
        if (prices.input === undefined && prices.output === undefined) return;

        // Model name: nearest heading inside the card
        const h = card.querySelector('h1,h2,h3,h4,h5,h6,[role="heading"]');
        const name = h ? h.textContent.trim() : null;
        if (!name) return;

        results.push({ name, ...prices });
    });

    return results;
}
"""


class OpenAIScraper(BaseScraper):
    provider = Provider.OPENAI
    source_url = "https://openai.com/api/pricing"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def scrape(self):
        """Try httpx → Playwright → static fallback."""
        from datetime import datetime, timezone
        from ai_price_monitor.models import ProviderPricing

        def _make_result(models):
            return ProviderPricing(
                provider=self.provider,
                source_url=self.source_url,
                scraped_at=datetime.now(timezone.utc),
                scrape_succeeded=True,
                fallback_used=False,
                models=models,
            )

        # 1. Try httpx (works if Cloudflare lets us through)
        try:
            html = self._fetch_html(self.source_url)
            models = self._parse_html(html)
            self._validate(models)
            logger.info("openai: scraped %d models via httpx", len(models))
            return _make_result(models)
        except Exception as exc:
            logger.info("OpenAI httpx fetch/parse failed (%s), trying Playwright…", exc)

        # 2. Playwright scrape
        try:
            models = self._scrape_playwright()
            self._validate(models)
            logger.info("openai: scraped %d models via Playwright", len(models))
            return _make_result(models)
        except Exception as pw_exc:
            logger.warning("OpenAI Playwright scrape failed (%s), using static fallback", pw_exc)
            return self.scrape_static()

    # ------------------------------------------------------------------
    # httpx path — kept for the (rare) case Cloudflare passes us through
    # ------------------------------------------------------------------

    def _parse(self, html: str) -> list[PriceRecord]:
        """Used by the base-class scrape() — delegates to _parse_html."""
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[PriceRecord]:
        """Parse static HTML using regex on price spans + heuristic model names."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        records: list[PriceRecord] = []

        # Each model card: find a heading then look for price spans in the same subtree
        for heading in soup.find_all(re.compile(r"^h[1-6]$")):
            model_name = heading.get_text(strip=True)
            if not model_name or len(model_name) > 80:
                continue

            card = heading.parent
            if card is None:
                continue

            prices: dict[str, float] = {}
            for span in card.find_all("span"):
                txt = span.get_text(strip=True)
                try:
                    if re.match(r"^Input:", txt, re.I) and "cached" not in txt.lower():
                        prices["input"] = _parse_price_text(txt)
                    elif re.match(r"^Cached input:", txt, re.I):
                        prices["cached"] = _parse_price_text(txt)
                    elif re.match(r"^Output:", txt, re.I):
                        prices["output"] = _parse_price_text(txt)
                except ValueError:
                    pass

            if "input" not in prices and "output" not in prices:
                continue

            model_id = _slug(model_name)
            records.append(
                PriceRecord(
                    model_id=model_id,
                    model_name=model_name,
                    provider=Provider.OPENAI,
                    tier=_classify_tier(model_id),
                    input_price_per_1m=prices.get("input", 0.0),
                    output_price_per_1m=prices.get("output", 0.0),
                    cache_read_price=prices.get("cached"),
                    currency="USD",
                )
            )

        if not records:
            raise ValueError("No pricing records found in OpenAI HTML")
        return records

    # ------------------------------------------------------------------
    # Playwright path
    # ------------------------------------------------------------------

    def _scrape_playwright(self) -> list[PriceRecord]:
        """Launch Playwright, wait for the page to render, and extract all visible card prices."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ImportError(
                "playwright is not installed. "
                "Run: pip install 'ai-price-monitor[playwright]' && playwright install chromium"
            ) from exc

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=_BROWSER_UA)
                page.goto(
                    self.source_url,
                    # timeout * 1000 converts seconds → ms; ×2 gives extra headroom
                    timeout=self.timeout * 2000,
                    wait_until="load",
                )
                page.wait_for_timeout(3000)

                records: list[PriceRecord] = []
                seen: set[str] = set()
                for card in page.evaluate(_EXTRACT_JS):
                    r = self._card_to_record(card)
                    if r and r.model_id not in seen:
                        seen.add(r.model_id)
                        records.append(r)

                if not records:
                    raise ValueError("No pricing cards found on OpenAI page via Playwright")
                return records
            finally:
                browser.close()

    def _card_to_record(self, card: dict) -> PriceRecord | None:
        """Convert a JS-extracted card dict to a PriceRecord."""
        name = (card.get("name") or "").strip()
        if not name:
            return None
        input_p = float(card.get("input") or 0.0)
        output_p = float(card.get("output") or 0.0)
        if input_p == 0.0 and output_p == 0.0:
            return None
        cached = card.get("cached")
        model_id = _slug(name)
        return PriceRecord(
            model_id=model_id,
            model_name=name,
            provider=Provider.OPENAI,
            tier=_classify_tier(model_id),
            input_price_per_1m=input_p,
            output_price_per_1m=output_p,
            cache_read_price=float(cached) if cached is not None else None,
            currency="USD",
        )
