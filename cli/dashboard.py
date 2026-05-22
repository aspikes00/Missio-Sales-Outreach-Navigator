from __future__ import annotations
from datetime import date
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from database.db import Database
from database.queries import get_all_brands_daily_stats, get_or_create_daily_stats, get_pipeline_by_brand, get_pipeline_counts

console = Console()

STATUS_ORDER = [
    "not_contacted",
    "connection_pending",
    "connected",
    "stage_1_sent",
    "stage_2_sent",
    "stage_3_sent",
    "needs_response",
    "booked",
    "not_interested",
    "do_not_contact",
]

STATUS_COLORS = {
    "not_contacted": "white",
    "connection_pending": "yellow",
    "connected": "cyan",
    "stage_1_sent": "blue",
    "stage_2_sent": "blue",
    "stage_3_sent": "blue",
    "needs_response": "bright_green",
    "booked": "green",
    "not_interested": "dim",
    "do_not_contact": "dim",
}


def render_dashboard(db: Database, brand_slug: Optional[str] = None):
    today = date.today().isoformat()

    with db.transaction() as conn:
        if brand_slug:
            all_stats = [get_or_create_daily_stats(conn, today, brand_slug)]
        else:
            all_stats = get_all_brands_daily_stats(conn, today)
        pipeline_by_brand = get_pipeline_by_brand(conn)

    console.print(f"\n[bold]Missio Outreach — {today}[/]\n")

    for stats in all_stats:
        t = Table(show_header=False, box=None, padding=(0, 1))
        t.add_column("Metric", style="bold", min_width=22)
        t.add_column("Value", justify="right")
        t.add_row("Connections sent", f"[cyan]{stats.connections_sent}[/]")
        t.add_row("Messages sent", f"[cyan]{stats.messages_sent}[/]")
        t.add_row("Replies received", f"[green]{stats.replies_received}[/]")
        t.add_row("Bookings", f"[bright_green]{stats.bookings_detected}[/]")
        t.add_row("Errors", f"[red]{stats.errors_encountered}[/]")

        console.print(Panel(t, title=f"[bold]Today — {stats.brand}[/]", border_style="blue"))

    # Pipeline per brand
    for brand_key, pipeline in pipeline_by_brand.items():
        if brand_slug and brand_key != brand_slug:
            continue
        pt = Table(title=f"Pipeline — {brand_key}", border_style="blue")
        pt.add_column("Status", style="bold")
        pt.add_column("Count", justify="right")
        for status in STATUS_ORDER:
            count = pipeline.get(status, 0)
            if count == 0:
                continue
            color = STATUS_COLORS.get(status, "white")
            flag = "  [bright_green]← ACTION REQUIRED[/]" if status == "needs_response" else ""
            pt.add_row(f"[{color}]{status}[/]", f"[{color}]{count}[/]" + flag)
        total = sum(pipeline.values())
        pt.add_row("[bold]TOTAL[/]", f"[bold]{total}[/]")
        console.print(pt)

    console.print()
