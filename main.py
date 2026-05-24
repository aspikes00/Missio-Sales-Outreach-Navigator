#!/usr/bin/env python3
from __future__ import annotations
import logging
import sys
from datetime import date
from pathlib import Path

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def _setup_file_logging(log_path: Path):
    from logging.handlers import RotatingFileHandler
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)


def _load_common() -> tuple:
    from config.settings import load_settings
    from database.db import Database
    settings = load_settings()
    _setup_file_logging(settings.log_path)
    db = Database(settings.db_path)
    db.initialize_schema()
    return settings, db


@click.group()
def cli():
    """Missio Sales Outreach Navigator — LinkedIn outreach agent."""
    pass


@cli.command()
@click.option("--brand", required=True, help="Brand slug (folder name under brands/).")
@click.option("--dry-run", is_flag=True, default=False,
              help="Generate and print messages without sending anything.")
def run(brand: str, dry_run: bool):
    """Execute today's LinkedIn outreach session for a brand."""
    settings, db = _load_common()
    brand_config = settings.load_brand(brand)

    from outreach.sequence import SequenceOrchestrator
    if dry_run:
        click.echo(f"[DRY RUN] Brand: {brand_config.name} | CTA: {brand_config.cta_type}")

    orchestrator = SequenceOrchestrator(db, settings, brand_config, dry_run=dry_run)
    result = orchestrator.run_daily_session()

    click.echo(f"\nSession complete — {brand_config.name}:")
    click.echo(f"  Connections sent:      {result.connections_sent}")
    click.echo(f"  Messages sent:         {result.messages_sent}")
    click.echo(f"  InMails sent:          {result.inmails_sent}")
    click.echo(f"  Replies detected:      {result.replies_detected}")
    click.echo(f"  Connections accepted:  {result.connections_accepted}")
    click.echo(f"  Leads reclassified:    {result.leads_reclassified}")
    click.echo(f"  Errors:                {result.errors}")
    if result.halted_early:
        click.echo(f"  [!] Halted early: {result.halt_reason}")


@cli.command("import")
@click.option("--file", "filepath", required=True, help="Path to CSV file with lead data.")
@click.option("--brand", required=True, help="Brand slug to assign these leads to.")
@click.option("--list-name", default=None, help="Optional label for this lead list (e.g. 'Q2 ICPs').")
def import_leads(filepath: str, brand: str, list_name: str):
    """Import leads from a CSV file and assign them to a brand."""
    settings, db = _load_common()
    _ = settings.load_brand(brand)  # validate brand exists

    from outreach.importer import import_from_csv
    click.echo(f"Importing leads from {filepath} → brand: {brand}")
    result = import_from_csv(filepath, db, brand=brand, source_list=list_name)

    click.echo(f"  Added:   {result.added}")
    click.echo(f"  Skipped: {result.skipped} (duplicates or invalid)")
    if result.errors:
        click.echo(f"  Errors:  {len(result.errors)}")
        for err in result.errors[:10]:
            click.echo(f"    - {err}")


@cli.command()
@click.option("--brand", default=None, help="Filter by brand slug (omit for all brands).")
def status(brand: str):
    """Show a live dashboard of your outreach pipeline and today's stats."""
    settings, db = _load_common()
    from cli.dashboard import render_dashboard
    render_dashboard(db, brand_slug=brand)


@cli.command()
@click.option("--brand", default=None, help="Filter by brand slug (omit for all brands).")
@click.option("--week", is_flag=True, default=False, help="Show the weekly report instead of daily.")
@click.option("--save", is_flag=True, default=False, help="Save the report to logs/reports/.")
def report(brand: str, week: bool, save: bool):
    """Generate a daily or weekly outreach report."""
    settings, db = _load_common()
    from reports.reporter import (
        generate_daily_report,
        generate_weekly_report,
        print_daily_report_rich,
        print_weekly_report_rich,
    )

    today = date.today().isoformat()

    if week:
        print_weekly_report_rich(db, brand_slug=brand)
        if save:
            week_num = date.today().isocalendar()[1]
            filename = f"{date.today().year}-week-{week_num:02d}"
            if brand:
                filename += f"-{brand}"
            save_path = settings.log_path.parent / "reports" / f"{filename}.txt"
            text = generate_weekly_report(db, brand_slug=brand, save_to=save_path)
            click.echo(f"\nSaved to: {save_path}")
    else:
        print_daily_report_rich(db, brand_slug=brand, today=today)
        if save:
            filename = today
            if brand:
                filename += f"-{brand}"
            save_path = settings.log_path.parent / "reports" / f"{filename}-daily.txt"
            text = generate_daily_report(db, brand_slug=brand, save_to=save_path, today=today)
            click.echo(f"\nSaved to: {save_path}")


@cli.command("mark-booked")
@click.option("--url", required=True, help="LinkedIn profile URL of the lead who booked a call.")
@click.option("--brand", required=True, help="Brand slug.")
@click.option("--notes", default=None, help="Optional notes about the booking.")
def mark_booked(url: str, brand: str, notes: str):
    """Manually mark a lead as having booked a call or signed up for a trial."""
    settings, db = _load_common()
    from database.queries import get_lead_by_url, mark_lead_booked, increment_daily_stat

    with db.transaction() as conn:
        lead = get_lead_by_url(conn, url)
        if not lead:
            click.echo(f"Lead not found in database: {url}")
            return
        mark_lead_booked(conn, lead.id)
        if notes:
            conn.execute("UPDATE leads SET notes = ? WHERE id = ?", (notes, lead.id))
        increment_daily_stat(conn, date.today().isoformat(), brand, "bookings_detected")

    click.echo(f"Marked {lead.full_name or lead.first_name or url} as booked.")


@cli.command("mark-dnc")
@click.option("--url", required=True, help="LinkedIn profile URL to add to do-not-contact list.")
def mark_dnc(url: str):
    """Mark a lead as do-not-contact. Stops all future outreach."""
    settings, db = _load_common()
    from database.queries import get_lead_by_url, update_lead_status

    with db.transaction() as conn:
        lead = get_lead_by_url(conn, url)
        if not lead:
            click.echo(f"Lead not found: {url}")
            return
        update_lead_status(conn, lead.id, "do_not_contact")

    click.echo(f"Marked {lead.full_name or url} as do-not-contact.")


@cli.command("sync-list")
@click.option("--brand", required=True, help="Brand slug.")
def sync_list(brand: str):
    """
    Read your Sales Navigator saved list and import any new leads into the database.

    Run this once to load your existing list, then again whenever you add more
    leads via populate-list. No CSV export needed.
    """
    settings, db = _load_common()
    brand_config = settings.load_brand(brand)

    if not brand_config.sales_nav_list_url or "YOUR_MISSIO" in brand_config.sales_nav_list_url:
        raise click.UsageError(
            "No list URL configured. Set sales_nav_list_url in brands/missio/brand.toml."
        )

    click.echo(f"Opening your Sales Navigator list for: {brand_config.name}")
    click.echo("Reading lead cards... (browser will open)")

    from linkedin.auth import ensure_authenticated
    from linkedin.browser import BrowserManager
    from linkedin.navigator import sync_leads_from_list
    from database.queries import insert_lead, url_exists
    from database.models import Lead

    with BrowserManager(settings) as browser:
        ensure_authenticated(
            browser.page, settings.linkedin_email, settings.linkedin_password
        )
        list_leads = sync_leads_from_list(browser.page, brand_config.sales_nav_list_url)

    added = skipped = 0
    for ll in list_leads:
        with db.transaction() as conn:
            if url_exists(conn, ll.linkedin_url):
                skipped += 1
                continue
            lead = Lead(
                id=None,
                linkedin_url=ll.linkedin_url,
                brand=brand,
                first_name=ll.first_name,
                last_name=ll.last_name,
                full_name=ll.full_name,
                title=ll.title,
                company_name=ll.company_name,
                location=ll.location,
                source_list=brand_config.sales_nav_list_name or "Sales Navigator",
            )
            insert_lead(conn, lead)
            added += 1

    click.echo(f"\nDone.")
    click.echo(f"  New leads imported: {added}")
    click.echo(f"  Already in DB:      {skipped}")
    click.echo(f"  Total in list:      {len(list_leads)}")
    if added > 0:
        click.echo(f"\n  Run option 2 (preview) or option 3 (go live) next.")


@cli.command("populate-list")
@click.option("--brand", required=True, help="Brand slug (reads search URL and list name from brand.toml).")
@click.option("--search-url", default=None,
              help="Override the Sales Navigator search URL (optional — defaults to brand.toml value).")
@click.option("--list-name", default=None,
              help="Override the list name (optional — defaults to brand.toml value).")
@click.option("--max", "max_per_session", default=200, show_default=True,
              help="Max leads to add per run. Safe to run daily until the list is full.")
@click.option("--start-page", default=1, show_default=True,
              help="Resume from a specific search results page number.")
def populate_list(brand: str, search_url: str, list_name: str, max_per_session: int, start_page: int):
    """
    Page through a Sales Navigator search and bulk-add results to your saved list.

    Runs at human speed with realistic delays. Safe to run daily.
    Use --max to control how many leads are added per session.
    Use --start-page to resume where you left off.

    Example:
      python main.py populate-list --brand missio
      python main.py populate-list --brand missio --max 100 --start-page 5
    """
    settings, db = _load_common()
    brand_config = settings.load_brand(brand)

    effective_search_url = search_url or brand_config.sales_nav_search_url
    effective_list_name = list_name or brand_config.sales_nav_list_name

    if not effective_search_url or "YOUR_SEARCH_PARAMS" in effective_search_url:
        raise click.UsageError(
            "No search URL configured. Either:\n"
            "  1. Set sales_nav_search_url in brands/missio/brand.toml\n"
            "  2. Pass --search-url 'https://www.linkedin.com/sales/search/people?...'"
        )
    if not effective_list_name or "YOUR LIST NAME" in effective_list_name:
        raise click.UsageError(
            "No list name configured. Either:\n"
            "  1. Set sales_nav_list_name in brands/missio/brand.toml\n"
            "  2. Pass --list-name 'Your Exact List Name'"
        )

    click.echo(f"Brand:       {brand_config.name}")
    click.echo(f"List name:   {effective_list_name}")
    click.echo(f"Max per run: {max_per_session} leads (~{max_per_session // 25} pages)")
    click.echo(f"Start page:  {start_page}")
    click.echo()
    click.echo("Opening browser... (this will be visible — that's intentional)")

    from linkedin.auth import ensure_authenticated
    from linkedin.browser import BrowserManager
    from linkedin.list_builder import SelectorOutdatedError, populate_list_from_search
    from safety.humanizer import Humanizer

    humanizer = Humanizer(
        min_delay=settings.min_delay_seconds,
        max_delay=settings.max_delay_seconds,
    )

    with BrowserManager(settings) as browser:
        ensure_authenticated(
            browser.page, settings.linkedin_email, settings.linkedin_password
        )

        try:
            result = populate_list_from_search(
                page=browser.page,
                search_url=effective_search_url,
                list_name=effective_list_name,
                humanizer=humanizer,
                max_per_session=max_per_session,
                start_page=start_page,
            )
        except SelectorOutdatedError as e:
            click.echo(f"\n[!] LinkedIn UI has changed — selector needs updating:\n{e}")
            click.echo("\nOpen an issue or update linkedin/selectors.py manually.")
            return

    click.echo(f"\nDone.")
    click.echo(f"  Leads added this run:  ~{result['added']}")
    click.echo(f"  Pages processed:       {result['pages_processed']}")
    click.echo(f"  Stopped because:       {result['stopped_reason']}")

    if result["stopped_reason"] == "session_limit_reached":
        click.echo(f"\n  Resume tomorrow with:")
        click.echo(f"  python main.py populate-list --brand {brand} --start-page {result['resume_from_page']}")
    elif result["stopped_reason"] in ("no_more_results", "no_next_page"):
        click.echo(f"\n  All available search results have been added to the list.")


@cli.command("list-brands")
def list_brands():
    """List all configured brands."""
    settings, _ = _load_common()
    brands = settings.list_brands()
    if not brands:
        click.echo("No brands configured. Create a folder under brands/ with a brand.toml file.")
        return
    click.echo("Configured brands:")
    for slug in brands:
        try:
            b = settings.load_brand(slug)
            click.echo(f"  {slug:<30} {b.name} ({b.cta_type})")
        except Exception:
            click.echo(f"  {slug:<30} (error loading brand.toml)")


if __name__ == "__main__":
    cli()
