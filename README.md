# 🤖 AI API 价格监控器

自动抓取并横向对比 **OpenAI**、**Anthropic (Claude)**、**Kimi (Moonshot)**、**DeepSeek** 四家 AI API 定价的 Python CLI 工具，支持迁移成本估算，并生成可视化 HTML / Markdown 报告。

[![CI](https://github.com/WilliamsSkywalker/ai-price-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/WilliamsSkywalker/ai-price-monitor/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 功能特性

- 🔍 **实时价格抓取** — 从各厂商官网抓取最新定价，抓取失败自动回退到内置静态数据
- 📊 **终端对比表格** — 按能力等级（便宜 / 标准 / 旗舰）分组展示
- 💰 **迁移成本计算器** — 估算迁移到任意模型的月度费用
- 📈 **价格变动检测** — 对比任意两份快照，自动标注涨价 / 降价
- 🌐 **HTML 可视化报告** — 内嵌 Chart.js 图表，单文件，无需服务器，双击即可打开
- 📄 **Markdown 报告** — 适配 GitHub / Notion / Obsidian
- ⏰ **定时监控** — 按可配置间隔自动运行
- 🛡️ **离线可用** — 内置静态价格，无网络也能跑演示

---

## 📦 安装

```bash
git clone https://github.com/WilliamsSkywalker/ai-price-monitor
cd ai-price-monitor
pip install -e .
```

**环境要求：** Python 3.9+

---

## 🚀 快速上手

```bash
# 1. 抓取最新价格（优先实时抓取，失败则使用内置数据）
ai-price-monitor fetch

# 2. 终端对比表格
ai-price-monitor compare

# 3. 估算月度费用
ai-price-monitor calculate --input-tokens 10000000 --output-tokens 3000000

# 4. 生成 HTML + Markdown 报告
ai-price-monitor report

# 5. 浏览器打开 HTML 报告
open reports/$(date +%Y-%m-%d)_report.html
```

**没有网络？没关系：**
```bash
ai-price-monitor fetch --force-static   # 使用内置静态价格
```

---

## 📋 命令说明

### `fetch` — 抓取并保存价格快照

```bash
ai-price-monitor fetch [OPTIONS]

Options:
  --force-static        跳过实时抓取，使用内置静态价格
  --provider, -p TEXT   只抓取指定厂商（可重复）
```

### `compare` — 终端价格对比表

```bash
ai-price-monitor compare [OPTIONS]

Options:
  --tier, -t TEXT       按等级过滤：cheap | standard | premium
  --sort, -s TEXT       排序字段（默认：output_price_per_1m）
  --vs TEXT             与指定日期（YYYY-MM-DD）快照对比差异
  --date, -d TEXT       使用指定日期的快照
  --provider, -p TEXT   按厂商过滤
```

### `calculate` — 月度成本估算

```bash
ai-price-monitor calculate [OPTIONS]

Options:
  --input-tokens, -i INT    月度输入 token 数（默认：10M）
  --output-tokens, -o INT   月度输出 token 数（默认：3M）
  --cache-read-tokens INT   月度缓存读取 token 数（默认：0）
  --tier, -t TEXT           按等级过滤结果
  --date, -d TEXT           使用指定日期的快照
```

### `report` — 生成 HTML + Markdown 报告

```bash
ai-price-monitor report [OPTIONS]

Options:
  --date, -d TEXT       使用指定日期的快照
  --output, -o PATH     输出目录（默认：reports/）
  --input-tokens INT    自定义用量（用于成本表）
  --output-tokens INT   自定义用量（用于成本表）
  --no-html             跳过 HTML 报告
  --no-md               跳过 Markdown 报告
```

### `history` — 查看历史快照列表

```bash
ai-price-monitor history
```

### `schedule` — 定时监控

```bash
ai-price-monitor schedule [OPTIONS]

Options:
  --interval INT        轮询间隔（分钟，默认：1440 = 每天）
  --force-static        使用静态价格代替实时抓取
  --no-report           每次抓取后跳过报告生成
```

### 全局标志

```bash
ai-price-monitor --no-color ...    # 禁用彩色输出
ai-price-monitor --json ...        # 以 JSON 格式输出结果
ai-price-monitor --verbose ...     # 启用调试日志
ai-price-monitor --quiet ...       # 静默模式
```

---

## 🏢 支持的厂商与模型

| 厂商 | 已追踪模型 | 定价页面 |
|------|-----------|---------|
| **OpenAI** | GPT-4o, GPT-4o mini, o1, o3-mini, GPT-4.1, GPT-4.1 mini | [openai.com/api/pricing](https://openai.com/api/pricing) |
| **Anthropic** | Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 3.5 | [anthropic.com/pricing](https://www.anthropic.com/pricing) |
| **Kimi (Moonshot)** | moonshot-v1-8k/32k/128k, kimi-latest | [platform.moonshot.cn/docs/pricing](https://platform.moonshot.cn/docs/pricing/chat) |
| **DeepSeek** | DeepSeek-V3 (chat), DeepSeek-R1 (reasoner) | [platform.deepseek.com/pricing](https://platform.deepseek.com/pricing) |

> Kimi 价格为人民币，按 `config/settings.toml` 中配置的汇率自动换算为美元。

---

## 📊 报告示例

运行 `ai-price-monitor report` 后，会在 `reports/` 目录生成：

- **`YYYY-MM-DD_report.html`** — 交互式 HTML 报告，包含：
  - 横向柱状图：各模型输出价格对比
  - 分组柱状图：各厂商输入 vs 输出价格
  - 折线图：历史价格趋势（多份快照时显示）
  - 实时成本计算器：调整 token 用量即时更新费用

- **`YYYY-MM-DD_report.md`** — Markdown 报告，包含：
  - 按等级分组的价格表
  - 与上次快照的价格变动 diff
  - 月度成本排名

---

## ⚙️ 配置

编辑 `config/settings.toml`：

```toml
[general]
usd_to_cny = 7.25          # Kimi CNY → USD 汇率
reports_dir = "reports"    # 报告输出目录
history_dir = "data/price_history"

[schedule]
interval_minutes = 1440    # schedule 模式的轮询间隔（默认每天）

[scraping]
timeout_seconds = 30       # HTTP 超时
max_retries = 3            # 失败重试次数
retry_delay_seconds = 2    # 重试间隔

[calculator]
default_input_tokens = 10_000_000   # 默认月度 input token 数
default_output_tokens = 3_000_000
```

也可以用环境变量覆盖（优先级高于 TOML）：

```bash
export AI_PRICE_MONITOR__GENERAL__USD_TO_CNY=7.30
export AI_PRICE_MONITOR__SCHEDULE__INTERVAL_MINUTES=720
```

---

## 🗂️ 项目结构

```
ai-price-monitor/
├── config/settings.toml          # 用户配置
├── data/
│   ├── static_prices.json        # 内置兜底价格
│   └── price_history/            # 自动生成的每日快照
├── reports/                      # 自动生成的报告
└── src/ai_price_monitor/
    ├── cli.py                    # Typer CLI
    ├── models.py                 # Pydantic 数据模型
    ├── scrapers/                 # 各厂商爬虫
    ├── storage.py                # 快照读写
    ├── comparator.py             # 价格 diff 逻辑
    ├── calculator.py             # 成本估算
    ├── renderer.py               # Rich 终端表格
    ├── reporter.py               # Markdown 报告
    └── html_reporter.py          # HTML + Chart.js 报告
```

---

## 🤝 贡献指南

### 更新静态价格

当厂商调价而爬虫尚未更新时，可手动更新 `data/static_prices.json` 并提 PR：

1. 在厂商定价页面找到最新价格
2. 修改 `data/static_prices.json` 中对应条目
3. 更新 `_comment` 字段注明日期
4. PR 标题格式：`chore: update static prices for <provider> (<date>)`

### 添加新厂商

1. 新建 `src/ai_price_monitor/scrapers/<provider>.py`，继承 `BaseScraper`
2. 在 `src/ai_price_monitor/scrapers/__init__.py` 注册
3. 在 `data/static_prices.json` 添加兜底数据
4. 在 `tests/test_scrapers.py` 添加测试

### 运行测试

```bash
pip install -e ".[dev]"
pytest
```

---

## 📜 License

MIT — 详见 [LICENSE](LICENSE)

---

*基于 [Typer](https://typer.tiangolo.com/)、[Rich](https://rich.readthedocs.io/)、[httpx](https://www.python-httpx.org/)、[BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)、[Pydantic](https://docs.pydantic.dev/) 和 [Chart.js](https://www.chartjs.org/) 构建。*

---

---

# 🤖 AI API Price Monitor

A Python CLI tool that automatically tracks and compares AI API pricing across **OpenAI**, **Anthropic (Claude)**, **Kimi (Moonshot)**, and **DeepSeek** — with migration cost estimation and visualized HTML/Markdown reports.

## ✨ Features

- 🔍 **Live price scraping** from provider websites with automatic fallback to bundled static prices
- 📊 **Terminal comparison tables** grouped by tier (cheap / standard / premium)
- 💰 **Migration cost calculator** — estimate monthly spend across all models
- 📈 **Price change detection** — diff any two snapshots to spot price cuts/hikes
- 🌐 **HTML reports** with interactive Chart.js visualizations (single-file, no server needed)
- 📄 **Markdown reports** for GitHub/Notion/Obsidian
- ⏰ **Scheduled monitoring** — run automatically at configurable intervals
- 🛡️ **Works offline** — bundled static prices let you demo without internet access

## 📦 Installation

```bash
git clone https://github.com/WilliamsSkywalker/ai-price-monitor
cd ai-price-monitor
pip install -e .
```

**Requirements:** Python 3.9+

## 🚀 Quick Start

```bash
ai-price-monitor fetch
ai-price-monitor compare
ai-price-monitor calculate --input-tokens 10000000 --output-tokens 3000000
ai-price-monitor report
open reports/$(date +%Y-%m-%d)_report.html
```

## 🏢 Supported Providers

| Provider | Models | Pricing Page |
|----------|--------|-------------|
| **OpenAI** | GPT-4o, GPT-4o mini, o1, o3-mini, GPT-4.1, GPT-4.1 mini | [openai.com/api/pricing](https://openai.com/api/pricing) |
| **Anthropic** | Claude Opus 4.5, Claude Sonnet 4.5, Claude Haiku 3.5 | [anthropic.com/pricing](https://www.anthropic.com/pricing) |
| **Kimi (Moonshot)** | moonshot-v1-8k/32k/128k, kimi-latest | [platform.moonshot.cn/docs/pricing](https://platform.moonshot.cn/docs/pricing/chat) |
| **DeepSeek** | DeepSeek-V3 (chat), DeepSeek-R1 (reasoner) | [platform.deepseek.com/pricing](https://platform.deepseek.com/pricing) |

## 📜 License

MIT — see [LICENSE](LICENSE)
