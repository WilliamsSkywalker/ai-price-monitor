"""Typer CLI entry point for ai-price-monitor."""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from typer import Option

from ai_price_monitor import __version__
from ai_price_monitor import config as cfg
from ai_price_monitor.calculator import estimate_all
from ai_price_monitor.comparator import diff_snapshots, filter_by_tier, sort_models
from ai_price_monitor.html_reporter import save_html_report
from ai_price_monitor.models import MonthlyUsage, Provider, Tier
from ai_price_monitor.renderer import (
    render_comparison_table,
    render_cost_table,
    render_diff,
    render_history_list,
    render_snapshot_status,
)
from ai_price_monitor.reporter import save_markdown_report
from ai_price_monitor.scrapers import run_all
from ai_price_monitor.storage import (
    list_snapshots,
    load_latest_snapshot,
    load_snapshot,
    make_snapshot,
    save_snapshot,
)

app = typer.Typer(
    name="ai-price-monitor",
    help="Monitor and compare AI API pricing across providers.",
    add_completion=False,
    rich_markup_mode="rich",
)

# Global state (set by callback)
_console: Console | None = None
_json_output: bool = False


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console()
    return _console


def _require_snapshot(snapshot_date: str | None) -> "PriceSnapshot":
    """Load latest or dated snapshot, exiting with an error if none found."""
    from ai_price_monitor.models import PriceSnapshot  # local to avoid circular at module level
    snapshot = load_snapshot(snapshot_date) if snapshot_date else load_latest_snapshot()
    if not snapshot:
        get_console().print("[red]No snapshots found. Run `ai-price-monitor fetch` first.[/red]")
        raise typer.Exit(1)
    return snapshot


@app.callback()
def main_callback(
    no_color: bool = Option(False, "--no-color", help="Disable colour output"),
    json_output: bool = Option(False, "--json", help="Output results as JSON"),
    verbose: bool = Option(False, "--verbose", "-v", help="Enable verbose logging"),
    quiet: bool = Option(False, "--quiet", "-q", help="Suppress informational output"),
):
    """AI API Price Monitor — fetch, compare, and report on AI API pricing."""
    global _console, _json_output
    _json_output = json_output

    log_level = logging.WARNING
    if verbose:
        log_level = logging.DEBUG
    elif quiet:
        log_level = logging.ERROR

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )
    _console = Console(no_color=no_color, quiet=quiet)


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------

@app.command()
def fetch(
    force_static: bool = Option(
        False, "--force-static", help="Skip live scraping; use built-in static prices"
    ),
    providers: Optional[list[str]] = Option(
        None, "--provider", "-p", help="Limit to specific providers (repeatable)"
    ),
):
    """Fetch prices from all providers and save a snapshot."""
    console = get_console()
    console.print(f"[bold cyan]🔍 Fetching prices...[/bold cyan] (force-static={force_static})")

    all_data = run_all(force_static=force_static)

    if providers:
        valid = {p.value for p in Provider}
        all_data = [p for p in all_data if p.provider.value in providers]
        invalid = set(providers) - valid
        if invalid:
            console.print(f"[yellow]Unknown providers: {', '.join(invalid)}[/yellow]")

    snapshot = make_snapshot(all_data)
    path = save_snapshot(snapshot)

    console.print(f"[green]✅ Snapshot saved:[/green] {path}")
    render_snapshot_status(snapshot, console)

    for p in all_data:
        status = "⚠️ fallback" if p.fallback_used else "✅"
        console.print(f"  {p.provider.value.upper()}: {len(p.models)} models {status}")

    if _json_output:
        print(snapshot.model_dump_json(indent=2))


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------

@app.command()
def compare(
    tier: Optional[str] = Option(None, "--tier", "-t", help="Filter by tier: cheap|standard|premium"),
    sort: str = Option("output_price_per_1m", "--sort", "-s", help="Sort field"),
    vs: Optional[str] = Option(None, "--vs", help="Compare against snapshot date (YYYY-MM-DD)"),
    snapshot_date: Optional[str] = Option(None, "--date", "-d", help="Use snapshot from this date"),
    providers: Optional[list[str]] = Option(None, "--provider", "-p"),
):
    """Show price comparison table in the terminal."""
    console = get_console()

    snapshot = _require_snapshot(snapshot_date)

    models = snapshot.get_all_models()

    if providers:
        models = [m for m in models if m.provider.value in providers]

    tier_filter: Tier | None = None
    if tier:
        try:
            tier_filter = Tier(tier)
        except ValueError:
            console.print(f"[red]Invalid tier {tier!r}. Choose from: cheap, standard, premium[/red]")
            raise typer.Exit(1)
    models = filter_by_tier(models, tier_filter)
    models = sort_models(models, sort_by=sort)

    render_snapshot_status(snapshot, console)
    render_comparison_table(models, console)

    if vs:
        old_snapshot = load_snapshot(vs)
        if not old_snapshot:
            console.print(f"[yellow]Snapshot for {vs} not found.[/yellow]")
        else:
            diff = diff_snapshots(old_snapshot, snapshot)
            render_diff(diff, console)

    if _json_output:
        print(json.dumps([m.model_dump() for m in models], indent=2, default=str))


# ---------------------------------------------------------------------------
# calculate
# ---------------------------------------------------------------------------

@app.command()
def calculate(
    input_tokens: int = Option(
        None, "--input-tokens", "-i", help="Monthly input token count"
    ),
    output_tokens: int = Option(
        None, "--output-tokens", "-o", help="Monthly output token count"
    ),
    cache_read_tokens: int = Option(0, "--cache-read-tokens", help="Monthly cache read tokens"),
    snapshot_date: Optional[str] = Option(None, "--date", "-d"),
    tier: Optional[str] = Option(None, "--tier", "-t"),
):
    """Estimate monthly migration costs for all models."""
    console = get_console()

    # Defaults from config
    input_tokens = input_tokens or cfg.get("calculator", "default_input_tokens", 10_000_000)
    output_tokens = output_tokens or cfg.get("calculator", "default_output_tokens", 3_000_000)

    usage = MonthlyUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
    )

    snapshot = _require_snapshot(snapshot_date)

    estimates = estimate_all(snapshot, usage)

    if tier:
        try:
            tier_filter = Tier(tier)
        except ValueError:
            console.print(f"[red]Invalid tier {tier!r}. Choose from: cheap, standard, premium[/red]")
            raise typer.Exit(1)
        estimates = [e for e in estimates if e.tier == tier_filter]

    console.print(
        f"[dim]Usage: {input_tokens:,} input + {output_tokens:,} output"
        f" + {cache_read_tokens:,} cache-read tokens/month[/dim]"
    )
    render_cost_table(estimates, console)

    if _json_output:
        print(json.dumps([e.model_dump() for e in estimates], indent=2, default=str))


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@app.command()
def report(
    snapshot_date: Optional[str] = Option(None, "--date", "-d"),
    output_dir: Optional[Path] = Option(None, "--output", "-o"),
    input_tokens: Optional[int] = Option(None, "--input-tokens"),
    output_tokens: Optional[int] = Option(None, "--output-tokens"),
    no_html: bool = Option(False, "--no-html", help="Skip HTML report"),
    no_md: bool = Option(False, "--no-md", help="Skip Markdown report"),
):
    """Generate Markdown and HTML pricing reports."""
    console = get_console()

    snapshot = _require_snapshot(snapshot_date)

    # Load previous snapshot for diff
    all_dates = list_snapshots()
    diff = None
    if len(all_dates) >= 2:
        current_idx = all_dates.index(snapshot.snapshot_date) if snapshot.snapshot_date in all_dates else 0
        older_date = all_dates[current_idx + 1] if current_idx + 1 < len(all_dates) else None
        if older_date:
            old_snap = load_snapshot(older_date)
            if old_snap:
                diff = diff_snapshots(old_snap, snapshot)

    # Load historical snapshots for trend chart
    historical = []
    for d in sorted(all_dates)[-10:]:  # last 10 snapshots
        s = load_snapshot(d)
        if s:
            historical.append(s)

    usage = None
    if input_tokens or output_tokens:
        usage = MonthlyUsage(
            input_tokens=input_tokens or cfg.get("calculator", "default_input_tokens", 10_000_000),
            output_tokens=output_tokens or cfg.get("calculator", "default_output_tokens", 3_000_000),
        )

    if not no_md:
        md_path = save_markdown_report(snapshot, diff, usage, output_dir)
        console.print(f"[green]📄 Markdown report:[/green] {md_path}")

    if not no_html:
        html_path = save_html_report(snapshot, diff, historical or None, output_dir)
        console.print(f"[green]🌐 HTML report:[/green] {html_path}")

    if _json_output:
        out = {}
        if not no_md:
            out["markdown"] = str(md_path)
        if not no_html:
            out["html"] = str(html_path)
        print(json.dumps(out))


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

@app.command()
def history():
    """List available price history snapshots."""
    console = get_console()
    dates = list_snapshots()
    render_history_list(dates, console)

    if _json_output:
        print(json.dumps(dates))


# ---------------------------------------------------------------------------
# schedule
# ---------------------------------------------------------------------------

@app.command()
def schedule(
    interval: int = Option(
        None, "--interval", help="Polling interval in minutes (default from config)"
    ),
    force_static: bool = Option(False, "--force-static"),
    run_report: bool = Option(True, "--report/--no-report", help="Generate report after each fetch"),
):
    """Run fetch (and optionally report) on a recurring schedule."""
    import time as _time

    console = get_console()
    interval = interval or cfg.get("schedule", "interval_minutes", 1440)

    console.print(
        f"[bold]⏰ Scheduler started[/bold] — interval: [cyan]{interval}[/cyan] minutes"
    )
    console.print("Press Ctrl+C to stop.\n")

    try:
        while True:
            console.print(f"[dim]{date.today()}[/dim] Running fetch...")
            try:
                all_data = run_all(force_static=force_static)
                snapshot = make_snapshot(all_data)
                path = save_snapshot(snapshot)
                console.print(f"[green]✅[/green] Saved: {path}")

                if run_report:
                    # Load diff
                    all_dates = list_snapshots()
                    diff = None
                    if len(all_dates) >= 2:
                        older = load_snapshot(all_dates[1])
                        if older:
                            diff = diff_snapshots(older, snapshot)
                    md_path = save_markdown_report(snapshot, diff)
                    html_path = save_html_report(snapshot, diff)
                    console.print(f"[dim]Reports: {md_path}, {html_path}[/dim]")

            except Exception as exc:
                console.print(f"[red]Error during scheduled fetch: {exc}[/red]")

            console.print(f"[dim]Next run in {interval} minutes...[/dim]")
            _time.sleep(interval * 60)
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler stopped.[/yellow]")


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------

@app.command()
def version():
    """Show version and exit."""
    console = get_console()
    console.print(f"ai-price-monitor v{__version__}")


if __name__ == "__main__":
    app()
