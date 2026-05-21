import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from database.db import Database
from database.queries import (
    get_all_brands_daily_stats,
    get_daily_stats_range,
    get_pipeline_by_brand,
    get_pipeline_counts,
)

logger = logging.getLogger(__name__)
console = Console()

STATUS_ORDER = [
    "not_contacted", "connection_pending", "connected",
    "stage_1_sent", "stage_2_sent", "stage_3_sent",
    "needs_response", "booked", "not_interested", "do_not_contact",
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


def generate_daily_report(
    db: Database,
    brand_slug: Optional[str] = None,
    save_to: Optional[Path] = None,
    today: Optional[str] = None,
) -> str:
    today = today or date.today().isoformat()
    lines = []

    header = f"Missio Outreach — Daily Report: {today}"
    lines.append("=" * 60)
    lines.append(f"  {header}")
    lines.append("=" * 60)

    with db.transaction() as conn:
        if brand_slug:
            from database.queries import get_or_create_daily_stats
            stats = get_or_create_daily_stats(conn, today, brand_slug)
            all_stats = [stats]
        else:
            all_stats = get_all_brands_daily_stats(conn, today)

        pipeline_by_brand = get_pipeline_by_brand(conn)

    if not all_stats:
        lines.append("\nNo activity recorded today.")
    else:
        total_conn = total_msg = total_replies = total_bookings = total_errors = 0

        for stats in all_stats:
            lines.append(f"\nBRAND: {stats.brand}")
            lines.append(f"  Connections sent:  {stats.connections_sent}")
            lines.append(f"  Messages sent:     {stats.messages_sent}")
            lines.append(f"  Replies received:  {stats.replies_received}")
            lines.append(f"  Bookings:          {stats.bookings_detected}")
            lines.append(f"  Errors:            {stats.errors_encountered}")

            if stats.brand in pipeline_by_brand:
                lines.append(f"\n  Pipeline ({stats.brand}):")
                for status in STATUS_ORDER:
                    count = pipeline_by_brand[stats.brand].get(status, 0)
                    if count > 0:
                        flag = "  ← ACTION REQUIRED" if status == "needs_response" else ""
                        lines.append(f"    {status:<22} {count:>4}{flag}")

            total_conn += stats.connections_sent
            total_msg += stats.messages_sent
            total_replies += stats.replies_received
            total_bookings += stats.bookings_detected
            total_errors += stats.errors_encountered

        if len(all_stats) > 1:
            lines.append(f"\n{'─' * 40}")
            lines.append("TOTAL ACROSS ALL BRANDS")
            lines.append(f"  Connections sent:  {total_conn}")
            lines.append(f"  Messages sent:     {total_msg}")
            lines.append(f"  Replies received:  {total_replies}")
            lines.append(f"  Bookings:          {total_bookings}")
            lines.append(f"  Errors:            {total_errors}")

    lines.append("\n" + "=" * 60)
    report_text = "\n".join(lines)

    if save_to:
        save_to.parent.mkdir(parents=True, exist_ok=True)
        save_to.write_text(report_text, encoding="utf-8")
        logger.info("Daily report saved to %s", save_to)

    return report_text


def generate_weekly_report(
    db: Database,
    brand_slug: Optional[str] = None,
    save_to: Optional[Path] = None,
    end_date: Optional[str] = None,
) -> str:
    end = datetime.strptime(end_date or date.today().isoformat(), "%Y-%m-%d")
    start = end - timedelta(days=6)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    days = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    day_labels = [(start + timedelta(days=i)).strftime("%a") for i in range(7)]

    lines = []
    lines.append("=" * 70)
    lines.append(f"  Missio Outreach — Weekly Report: {start_str} → {end_str}")
    lines.append("=" * 70)

    with db.transaction() as conn:
        all_stats = get_daily_stats_range(conn, start_str, end_str, brand=brand_slug)

    # Index stats by (date, brand)
    stats_index: dict[tuple[str, str], object] = {}
    brands_seen = set()
    for s in all_stats:
        stats_index[(s.date, s.brand)] = s
        brands_seen.add(s.brand)

    brands_to_show = sorted(brands_seen) if brands_seen else ([brand_slug] if brand_slug else [])

    if not brands_to_show:
        lines.append("\nNo data found for this period.")
        lines.append("=" * 70)
        return "\n".join(lines)

    col_w = 6
    header_row = f"{'':22}" + "".join(f"{d:>{col_w}}" for d in day_labels) + f"{'TOTAL':>{col_w+1}}"

    for brand in brands_to_show:
        lines.append(f"\nBRAND: {brand}")
        lines.append(header_row)
        lines.append("─" * len(header_row))

        metrics = [
            ("Connections", "connections_sent"),
            ("Messages", "messages_sent"),
            ("Replies", "replies_received"),
            ("Bookings", "bookings_detected"),
            ("Errors", "errors_encountered"),
        ]

        for label, field in metrics:
            row_vals = []
            total = 0
            for d in days:
                s = stats_index.get((d, brand))
                val = getattr(s, field, 0) if s else 0
                row_vals.append(val)
                total += val
            row = f"  {label:<20}" + "".join(f"{v:>{col_w}}" for v in row_vals) + f"{total:>{col_w+1}}"
            lines.append(row)

    lines.append("\n" + "=" * 70)
    report_text = "\n".join(lines)

    if save_to:
        save_to.parent.mkdir(parents=True, exist_ok=True)
        save_to.write_text(report_text, encoding="utf-8")
        logger.info("Weekly report saved to %s", save_to)

    return report_text


def print_daily_report_rich(db: Database, brand_slug: Optional[str] = None, today: Optional[str] = None):
    today = today or date.today().isoformat()

    with db.transaction() as conn:
        if brand_slug:
            from database.queries import get_or_create_daily_stats
            all_stats = [get_or_create_daily_stats(conn, today, brand_slug)]
        else:
            all_stats = get_all_brands_daily_stats(conn, today)
        pipeline_by_brand = get_pipeline_by_brand(conn)

    console.print(f"\n[bold blue]Missio Outreach — Daily Report: {today}[/]\n")

    for stats in all_stats:
        t = Table(show_header=False, box=None, padding=(0, 1))
        t.add_column("Metric", style="bold", min_width=22)
        t.add_column("Value", justify="right")
        t.add_row("Connections sent", f"[cyan]{stats.connections_sent}[/]")
        t.add_row("Messages sent", f"[cyan]{stats.messages_sent}[/]")
        t.add_row("Replies received", f"[green]{stats.replies_received}[/]")
        t.add_row("Bookings", f"[bright_green]{stats.bookings_detected}[/]")
        t.add_row("Errors", f"[red]{stats.errors_encountered}[/]")

        panel = Panel(t, title=f"[bold]{stats.brand}[/]", border_style="blue")
        console.print(panel)

        if stats.brand in pipeline_by_brand:
            pt = Table(title=f"Pipeline — {stats.brand}", border_style="blue")
            pt.add_column("Status", style="bold")
            pt.add_column("Count", justify="right")
            for status in STATUS_ORDER:
                count = pipeline_by_brand[stats.brand].get(status, 0)
                if count == 0:
                    continue
                color = STATUS_COLORS.get(status, "white")
                flag = " ← ACTION REQUIRED" if status == "needs_response" else ""
                pt.add_row(f"[{color}]{status}[/]", f"[{color}]{count}[/]" + flag)
            console.print(pt)
            console.print()


def print_weekly_report_rich(db: Database, brand_slug: Optional[str] = None, end_date: Optional[str] = None):
    end = datetime.strptime(end_date or date.today().isoformat(), "%Y-%m-%d")
    start = end - timedelta(days=6)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")
    days = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    day_labels = [(start + timedelta(days=i)).strftime("%a %-d") for i in range(7)]

    with db.transaction() as conn:
        all_stats = get_daily_stats_range(conn, start_str, end_str, brand=brand_slug)

    stats_index: dict[tuple[str, str], object] = {}
    brands_seen = set()
    for s in all_stats:
        stats_index[(s.date, s.brand)] = s
        brands_seen.add(s.brand)

    brands_to_show = sorted(brands_seen) if brands_seen else ([brand_slug] if brand_slug else [])

    console.print(f"\n[bold blue]Missio Outreach — Weekly Report: {start_str} → {end_str}[/]\n")

    for brand in brands_to_show:
        t = Table(title=f"[bold]{brand}[/]", border_style="blue")
        t.add_column("Metric", style="bold", min_width=16)
        for label in day_labels:
            t.add_column(label, justify="right", min_width=6)
        t.add_column("Total", justify="right", style="bold", min_width=6)

        metrics = [
            ("Connections", "connections_sent", "cyan"),
            ("Messages", "messages_sent", "cyan"),
            ("Replies", "replies_received", "green"),
            ("Bookings", "bookings_detected", "bright_green"),
            ("Errors", "errors_encountered", "red"),
        ]

        for label, field, color in metrics:
            vals = []
            total = 0
            for d in days:
                s = stats_index.get((d, brand))
                val = getattr(s, field, 0) if s else 0
                vals.append(f"[{color}]{val}[/]" if val > 0 else "[dim]—[/]")
                total += val
            t.add_row(label, *vals, f"[bold {color}]{total}[/]" if total > 0 else "[dim]0[/]")

        console.print(t)
        console.print()
