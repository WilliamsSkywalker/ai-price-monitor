"""Tests for scraper static fallback and parsing logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_price_monitor.models import Provider, ProviderPricing
from ai_price_monitor.scrapers.anthropic import AnthropicScraper
from ai_price_monitor.scrapers.deepseek import DeepSeekScraper
from ai_price_monitor.scrapers.kimi import KimiScraper
from ai_price_monitor.scrapers.openai import OpenAIScraper

FIXTURES = Path(__file__).parent / "fixtures"


def _html(name: str) -> str:
    p = FIXTURES / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""


# ---------------------------------------------------------------------------
# Static fallback
# ---------------------------------------------------------------------------

def test_openai_static_fallback():
    scraper = OpenAIScraper()
    result = scraper.scrape_static()
    assert isinstance(result, ProviderPricing)
    assert result.provider == Provider.OPENAI
    assert result.fallback_used is True
    assert len(result.models) > 0
    for m in result.models:
        assert m.input_price_per_1m >= 0
        assert m.output_price_per_1m >= 0


def test_anthropic_static_fallback():
    scraper = AnthropicScraper()
    result = scraper.scrape_static()
    assert result.provider == Provider.ANTHROPIC
    assert result.fallback_used is True
    assert any("claude" in m.model_id for m in result.models)


def test_kimi_static_fallback():
    scraper = KimiScraper()
    result = scraper.scrape_static()
    assert result.provider == Provider.KIMI
    assert result.fallback_used is True
    assert len(result.models) > 0


def test_deepseek_static_fallback():
    scraper = DeepSeekScraper()
    result = scraper.scrape_static()
    assert result.provider == Provider.DEEPSEEK
    assert result.fallback_used is True
    assert len(result.models) > 0


# ---------------------------------------------------------------------------
# Fallback on parse failure
# ---------------------------------------------------------------------------

def test_scraper_falls_back_on_network_error():
    scraper = OpenAIScraper()
    with patch.object(scraper, "_fetch_html", side_effect=RuntimeError("network down")):
        result = scraper.scrape()
    assert result.fallback_used is True
    assert result.scrape_succeeded is False
    assert len(result.models) > 0


def test_scraper_falls_back_on_parse_error():
    scraper = AnthropicScraper()
    with patch.object(scraper, "_fetch_html", return_value="<html><body>no data</body></html>"):
        result = scraper.scrape()
    # Empty parse should trigger fallback
    assert result.fallback_used is True


# ---------------------------------------------------------------------------
# HTML table parsing (if fixture files present)
# ---------------------------------------------------------------------------

def test_openai_parse_next_data():
    """Test OpenAI parser with embedded __NEXT_DATA__ JSON."""
    import json
    next_data = {
        "props": {
            "models": [
                {
                    "slug": "gpt-4o",
                    "name": "GPT-4o",
                    "inputPrice": 2.50,
                    "outputPrice": 10.00,
                    "cachedInputPrice": 1.25,
                    "contextWindow": 128000,
                }
            ]
        }
    }
    html = (
        f'<html><head><script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(next_data)}</script></head></html>"
    )
    scraper = OpenAIScraper()
    records = scraper._parse(html)
    assert len(records) == 1
    assert records[0].model_id == "gpt-4o"
    assert records[0].input_price_per_1m == 2.50
    assert records[0].output_price_per_1m == 10.00


def test_anthropic_parse_table():
    html = """
    <html><body>
    <table>
      <tr><th>Model</th><th>Input</th><th>Output</th><th>Context</th></tr>
      <tr><td>Claude Sonnet 4.5</td><td>$3 / MTok</td><td>$15 / MTok</td><td>200K</td></tr>
      <tr><td>Claude Haiku 3.5</td><td>$0.80 / MTok</td><td>$4 / MTok</td><td>200K</td></tr>
    </table>
    </body></html>
    """
    scraper = AnthropicScraper()
    records = scraper._parse(html)
    assert len(records) == 2
    sonnet = next(r for r in records if "sonnet" in r.model_id.lower())
    assert sonnet.input_price_per_1m == pytest.approx(3.00)
    assert sonnet.output_price_per_1m == pytest.approx(15.00)


def test_kimi_parse_table():
    html = """
    <html><body>
    <table>
      <tr><th>模型</th><th>输入</th><th>输出</th></tr>
      <tr><td>moonshot-v1-8k</td><td>¥1.2</td><td>¥1.2</td></tr>
      <tr><td>moonshot-v1-32k</td><td>¥2.4</td><td>¥2.4</td></tr>
    </table>
    </body></html>
    """
    scraper = KimiScraper()
    records = scraper._parse(html)
    assert len(records) == 2
    m8k = next(r for r in records if "8k" in r.model_id.lower())
    assert m8k.currency == "CNY"
    assert m8k.input_price_per_1m == pytest.approx(1.2 / 7.25, rel=0.01)


def test_deepseek_parse_table():
    html = """
    <html><body>
    <table>
      <tr><th>Model</th><th>Input (cache miss)</th><th>Cache Hit</th><th>Output</th></tr>
      <tr><td>deepseek-chat</td><td>$0.27</td><td>$0.07</td><td>$1.10</td></tr>
    </table>
    </body></html>
    """
    scraper = DeepSeekScraper()
    records = scraper._parse(html)
    assert len(records) >= 1
    chat = next((r for r in records if "chat" in r.model_id.lower()), None)
    if chat:
        assert chat.input_price_per_1m == pytest.approx(0.27)
        assert chat.output_price_per_1m == pytest.approx(1.10)


# ---------------------------------------------------------------------------
# run_all integration
# ---------------------------------------------------------------------------

def test_run_all_static():
    from ai_price_monitor.scrapers import run_all
    results = run_all(force_static=True)
    assert len(results) == 4
    providers = {r.provider for r in results}
    assert providers == {Provider.OPENAI, Provider.ANTHROPIC, Provider.KIMI, Provider.DEEPSEEK}
    for r in results:
        assert r.fallback_used is True
        assert len(r.models) > 0
