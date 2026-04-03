"""Rich terminal table renderer for price data."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text

from ai_price_monitor.models import (
    CostEstimate,
    PriceDiff,
    PriceRecord,
    PriceSnapshot,
    Provider,
    Tier,
)

_TIER_STYLE = {
    Tier.CHEAP: "green",
    Tier.STANDARD: "yellow",
    Tier.PREMIUM: "red",
}
_TIER_EMOJI = {
    Tier.CHEAP: "💚",
    Tier.STANDARD: "🟡",
    Tier.PREMIUM: "🔴",
}
_PROVIDER_COLOR = {
    Provider.OPENAI: "cyan",
    Provider.ANTHROPIC: "magenta",
    Provider.KIMI: "blue",
    Provider.DEEPSEEK: "green",
}


def _fmt_price(val: float | None, decimals: int = 4) -> str:
    if val is None:
        return "-"
    return f"${val:.{decimals}f}"


def _fmt_context(tokens: int | None) -> str:
    if tokens is None:
        return "-"
    if tokens >= 1_000_000:
        return f"{tokens // 1_000_000}M"
    return f"{tokens // 1000}K"


def render_comparison_table(
    models: list[PriceRecord],
    console: Console,
    group_by_tier: bool = True,
) -> None:
    """Render a price comparison table to the terminal."""
    if not models:
        console.print("[yellow]No models to display.[/yellow]")
        return

    table = Table(
        title="🤖 AI API Price Comparison",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white",
        expand=True,
    )
    table.add_column("Provider", style="bold", min_width=10)
    table.add_column("Model", min_width=20)
    table.add_column("Tier", min_width=8, justify="center")
    table.add_column("Input $/1M", justify="right", min_width=11)
    table.add_column("Output $/1M", justify="right", min_width=12)
    table.add_column("Cache Read", justify="right", min_width=11)
    table.add_column("Context", justify="right", min_width=8)

    # Group by tier if requested
    if group_by_tier:
        for tier in Tier:
            tier_models = [m for m in models if m.tier == tier]
            if not tier_models:
                continue
            # Add a section separator row
            table.add_section()
            for m in tier_models:
                _add_model_row(table, m)
    else:
        for m in models:
            _add_model_row(table, m)

    console.print(table)


def _add_model_row(table: Table, m: PriceRecord) -> None:
    tier_text = f"{_TIER_EMOJI[m.tier]} {m.tier.value}"
    provider_style = _PROVIDER_COLOR.get(m.provider, "white")
    table.add_row(
        Text(m.provider.value.upper(), style=provider_style),
        m.model_name,
        Text(tier_text, style=_TIER_STYLE[m.tier]),
        _fmt_price(m.input_price_per_1m),
        _fmt_price(m.output_price_per_1m),
        _fmt_price(m.cache_read_price),
        _fmt_context(m.context_window),
    )


def render_cost_table(estimates: list[CostEstimate], console: Console) -> None:
    """Render migration cost estimates as a ranked table."""
    table = Table(
        title="💰 Monthly Cost Estimates",
        box=box.ROUNDED,
        header_style="bold white",
        expand=True,
    )
    table.add_column("#", justify="right", min_width=3)
    table.add_column("Provider", style="bold", min_width=10)
    table.add_column("Model", min_width=22)
    table.add_column("Tier", min_width=8, justify="center")
    table.add_column("Input Cost", justify="right", min_width=11)
    table.add_column("Output Cost", justify="right", min_width=12)
    table.add_column("Cache Cost", justify="right", min_width=11)
    table.add_column("Total/Month", justify="right", min_width=12, style="bold")

    for rank, est in enumerate(estimates, start=1):
        provider_style = _PROVIDER_COLOR.get(est.provider, "white")
        tier_emoji = _TIER_EMOJI.get(est.tier, "")
        total_style = "bold green" if rank == 1 else ("bold yellow" if rank <= 3 else "")
        table.add_row(
            str(rank),
            Text(est.provider.value.upper(), style=provider_style),
            est.model_name,
            f"{tier_emoji} {est.tier.value}",
            f"${est.input_cost:.2f}",
            f"${est.output_cost:.2f}",
            f"${est.cache_cost:.2f}",
            Text(f"${est.monthly_cost_usd:.2f}", style=total_style),
        )

    console.print(table)


def render_diff(diff: PriceDiff, console: Console) -> None:
    """Render a PriceDiff to terminal."""
    if not diff.has_changes:
        console.print(f"[green]✅ No price changes between {diff.old_date} and {diff.new_date}[/green]")
        return

    console.print(f"\n[bold]📊 Price Changes: {diff.old_date} → {diff.new_date}[/bold]\n")

    if diff.added_models:
        console.print(f"[bold green]✨ New Models ({len(diff.added_models)}):[/bold green]")
        for m in diff.added_models:
            console.print(f"  + {m.provider.value} / {m.model_name}")

    if diff.removed_models:
        console.print(f"\n[bold red]🗑️  Removed Models ({len(diff.removed_models)}):[/bold red]")
        for m in diff.removed_models:
            console.print(f"  - {m.provider.value} / {m.model_name}")

    if diff.changed_models:
        table = Table(box=box.SIMPLE, header_style="bold white")
        table.add_column("Provider")
        table.add_column("Model")
        table.add_column("Field")
        table.add_column("Old", justify="right")
        table.add_column("New", justify="right")
        table.add_column("Change", justify="right")

        for ch in diff.changed_models:
            direction = "📉" if ch.pct_change < 0 else "📈"
            style = "green" if ch.pct_change < 0 else "red"
            table.add_row(
                ch.provider.value.upper(),
                ch.model_name,
                ch.field,
                f"${ch.old_value:.4f}",
                f"${ch.new_value:.4f}",
                Text(f"{direction} {ch.pct_change:+.1f}%", style=style),
            )

        console.print(f"\n[bold yellow]🔄 Price Changes ({len(diff.changed_models)}):[/bold yellow]")
        console.print(table)


def render_snapshot_status(snapshot: PriceSnapshot, console: Console) -> None:
    """Render scrape status summary."""
    parts = []
    for p in snapshot.providers:
        status = "⚠️(fallback)" if p.fallback_used else "✅"
        parts.append(f"{p.provider.value.capitalize()} {status}")
    console.print(f"[dim]Scrape status: {' | '.join(parts)}[/dim]")


def render_history_list(dates: list[str], console: Console) -> None:
    """Render list of available snapshots."""
    if not dates:
        console.print("[yellow]No snapshots found.[/yellow]")
        return
    table = Table(title="📁 Price History Snapshots", box=box.SIMPLE)
    table.add_column("#", justify="right")
    table.add_column("Date")
    table.add_column("Status")
    for i, d in enumerate(dates, 1):
        table.add_row(str(i), d, "✅")
    console.print(table)
