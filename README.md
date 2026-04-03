# 🤖 AI API Price Monitor

A Python CLI tool that automatically tracks and compares AI API pricing across **OpenAI**, **Anthropic (Claude)**, **Kimi (Moonshot)**, and **DeepSeek** — with migration cost estimation and visualized HTML/Markdown reports.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ Features

- 🔍 **Live price scraping** from provider websites with automatic fallback to bundled static prices
- 📊 **Terminal comparison tables** grouped by tier (cheap / standard / premium)
- 💰 **Migration cost calculator** — estimate monthly spend across all models
- 📈 **Price change detection** — diff any two snapshots to spot price cuts/hikes
- 🌐 **HTML reports** with interactive Chart.js visualizations (single-file, no server needed)
- 📄 **Markdown reports** for GitHub/Notion/Obsidian
- ⏰ **Scheduled monitoring** — run automatically at configurable intervals
- 🛡️ **Works offline** — bundled static prices let you demo without internet access

---

## 📦 Installation

```bash
git clone https://github.com/WilliamsSkywalker/ai-price-monitor
cd ai-price-monitor
pip install -e .
```

**Requirements:** Python 3.11+

---

## 🚀 Quick Start

```bash
# 1. Fetch latest prices (uses live scraping, falls back to bundled data)
ai-price-monitor fetch

# 2. Compare prices in terminal
ai-price-monitor compare

# 3. Estimate monthly costs for your usage
ai-price-monitor calculate --input-tokens 10000000 --output-tokens 3000000

# 4. Generate HTML + Markdown reports
ai-price-monitor report

# 5. Open the HTML report in your browser
open reports/$(date +%Y-%m-%d)_report.html
```

**No internet? No problem:**
```bash
ai-price-monitor fetch --force-static   # Uses bundled prices
```

---

## 📋 All Commands

### `fetch` — Scrape and save a price snapshot

```bash
ai-price-monitor fetch [OPTIONS]

Options:
  --force-static        Skip live scraping; use built-in static prices
  --provider, -p TEXT   Limit to specific providers (repeatable)
```

### `compare` — Terminal price comparison table

```bash
ai-price-monitor compare [OPTIONS]

Options:
  --tier, -t TEXT       Filter by tier: cheap | standard | premium
  --sort, -s TEXT       Sort by field (default: output_price_per_1m)
  --vs TEXT             Compare vs a specific date (YYYY-MM-DD) to show diffs
  --date, -d TEXT       Use a specific snapshot date
  --provider, -p TEXT   Filter by provider(s)
```

### `calculate` — Monthly cost estimator

```bash
ai-price-monitor calculate [OPTIONS]

Options:
  --input-tokens, -i INT    Monthly input token count (default: 10M)
  --output-tokens, -o INT   Monthly output token count (default: 3M)
  --cache-read-tokens INT   Monthly cache-read token count (default: 0)
  --tier, -t TEXT           Filter results by tier
  --date, -d TEXT           Use a specific snapshot date
```

### `report` — Generate HTML + Markdown reports

```bash
ai-price-monitor report [OPTIONS]

Options:
  --date, -d TEXT       Use a specific snapshot date
  --output, -o PATH     Output directory (default: reports/)
  --input-tokens INT    Custom usage for cost table
  --output-tokens INT   Custom usage for cost table
  --no-html             Skip HTML report generation
  --no-md               Skip Markdown report generation
```

### `history` — List available snapshots

```bash
ai-price-monitor history
```

### `schedule` — Scheduled monitoring

```bash
ai-price-monitor schedule [OPTIONS]

Options:
  --interval INT        Polling interval in minutes (default: 1440 = daily)
  --force-static        Use static prices instead of scraping
  --no-report           Skip report generation after each fetch
```

### Global Flags

```bash
ai-price-monitor --no-color ...    # Disable colour output
ai-price-monitor --json ...        # Output results as JSON
ai-price-monitor --verbose ...     # Enable debug logging
ai-price-monitor --quiet ...       # Suppress informational output
```

---

## 🏢 Supported Providers & Models

| Provider | Models Tracked | Pricing Page |
|----------|---------------|-------------|
| **OpenAI** | GPT-4o, GPT-4o mini, o1, o3-mini, GPT-4.1, GPT-4.1 mini | [openai.com/api/pricing](https://openai.com/api/pricing) |
| **Anthropic** | Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 3.5 | [anthropic.com/pricing](https://www.anthropic.com/pricing) |
| **Kimi (Moonshot)** | moonshot-v1-8k/32k/128k, kimi-latest | [platform.moonshot.cn/docs/pricing](https://platform.moonshot.cn/docs/pricing/chat) |
| **DeepSeek** | DeepSeek-V3 (chat), DeepSeek-R1 (reasoner) | [platform.deepseek.com/pricing](https://platform.deepseek.com/pricing) |

> Kimi prices are in CNY and converted to USD using the exchange rate in `config/settings.toml`.

---

## 📊 Report Examples

After running `ai-price-monitor report`, you'll find:

- **`reports/YYYY-MM-DD_report.html`** — Interactive HTML with Chart.js charts:
  - Horizontal bar chart: output price by model
  - Grouped bar chart: input vs output by provider
  - Line chart: historical price trends (when multiple snapshots exist)
  - Live cost calculator: adjust token counts and see costs update in real-time

- **`reports/YYYY-MM-DD_report.md`** — Markdown report with:
  - Price table by tier
  - Price change diff vs previous snapshot
  - Monthly cost rankings

---

## ⚙️ Configuration

Edit `config/settings.toml` to customise behaviour:

```toml
[general]
usd_to_cny = 7.25          # Exchange rate for Kimi CNY → USD conversion
reports_dir = "reports"    # Where to save reports
history_dir = "data/price_history"

[schedule]
interval_minutes = 1440    # How often to run in `schedule` mode (default: daily)

[scraping]
timeout_seconds = 30       # HTTP timeout
max_retries = 3            # Retry attempts on failure
retry_delay_seconds = 2    # Wait between retries

[calculator]
default_input_tokens = 10_000_000   # Default usage for cost estimates
default_output_tokens = 3_000_000
```

You can also use environment variables (takes priority over TOML):

```bash
export AI_PRICE_MONITOR__GENERAL__USD_TO_CNY=7.30
export AI_PRICE_MONITOR__SCHEDULE__INTERVAL_MINUTES=720
```

---

## 🗂️ Project Structure

```
ai-price-monitor/
├── config/settings.toml          # User configuration
├── data/
│   ├── static_prices.json        # Bundled fallback prices
│   └── price_history/            # Auto-generated daily snapshots
├── reports/                      # Auto-generated reports
└── src/ai_price_monitor/
    ├── cli.py                    # Typer CLI
    ├── models.py                 # Pydantic data models
    ├── scrapers/                 # Per-provider scrapers
    ├── storage.py                # Snapshot I/O
    ├── comparator.py             # Price diff logic
    ├── calculator.py             # Cost estimation
    ├── renderer.py               # Rich terminal tables
    ├── reporter.py               # Markdown reports
    └── html_reporter.py          # HTML + Chart.js reports
```

---

## 🤝 Contributing

### Updating Static Prices

When a provider changes their pricing and the scraper hasn't been updated yet, update `data/static_prices.json` manually and open a PR:

1. Find the new prices on the provider's pricing page
2. Edit the relevant entry in `data/static_prices.json`
3. Update the `_comment` field with the date
4. Submit a PR with the title: `chore: update static prices for <provider> (<date>)`

### Adding a New Provider

1. Create `src/ai_price_monitor/scrapers/<provider>.py` extending `BaseScraper`
2. Register it in `src/ai_price_monitor/scrapers/__init__.py`
3. Add fallback data to `data/static_prices.json`
4. Add tests in `tests/test_scrapers.py`

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

---

## 📜 License

MIT — see [LICENSE](LICENSE)

---

*Built with [Typer](https://typer.tiangolo.com/), [Rich](https://rich.readthedocs.io/), [httpx](https://www.python-httpx.org/), [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/), [Pydantic](https://docs.pydantic.dev/), and [Chart.js](https://www.chartjs.org/).*
