from datetime import date

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from database.db import Database
from database.queries import get_or_create_daily_stats, get_pipeline_counts

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


def render_dashboard(db: Database):
    today = date.today().isoformat()

    with db.transaction() as conn:
        stats = get_or_create_daily_stats(conn, today)
        pipeline = get_pipeline_counts(conn)

    # Today's stats panel
    stats_table = Table(show_header=False, box=None, padding=(0, 1))
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value", justify="right")

    conn_pct = f"{stats.connections_sent} sent"
    msg_pct = f"{stats.messages_sent} sent"

    stats_table.add_row("Connections today", f"[cyan]{conn_pct}[/]")
    stats_table.add_row("Messages today", f"[cyan]{msg_pct}[/]")
    stats_table.add_row("Replies received", f"[green]{stats.replies_received}[/]")
    stats_table.add_row("Bookings", f"[bright_green]{stats.bookings_detected}[/]")
    stats_table.add_row("Errors", f"[red]{stats.errors_encountered}[/]")

    stats_panel = Panel(stats_table, title=f"[bold]Today — {today}[/]", border_style="blue")

    # Pipeline table
    pipeline_table = Table(title="Lead Pipeline", border_style="blue")
    pipeline_table.add_column("Status", style="bold")
    pipeline_table.add_column("Count", justify="right")

    for status in STATUS_ORDER:
        count = pipeline.get(status, 0)
        if count == 0:
            continue
        color = STATUS_COLORS.get(status, "white")
        pipeline_table.add_row(f"[{color}]{status}[/]", f"[{color}]{count}[/]")

    total = sum(pipeline.values())
    pipeline_table.add_row("[bold]TOTAL[/]", f"[bold]{total}[/]")

    console.print()
    console.print(stats_panel)
    console.print(pipeline_table)
    console.print()
