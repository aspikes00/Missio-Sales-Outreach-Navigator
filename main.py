#!/usr/bin/env python3
import logging
import sys
from pathlib import Path

import click

# Set up logging before any imports that might log
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


@click.group()
def cli():
    """Missio Sales Outreach Navigator — LinkedIn outreach agent."""
    pass


@cli.command()
@click.option("--dry-run", is_flag=True, default=False,
              help="Generate messages and print them without sending anything.")
def run(dry_run: bool):
    """Execute today's LinkedIn outreach session."""
    from config.settings import load_settings
    from database.db import Database
    from outreach.sequence import SequenceOrchestrator

    settings = load_settings()
    _setup_file_logging(settings.log_path)

    db = Database(settings.db_path)
    db.initialize_schema()

    if dry_run:
        click.echo("[DRY RUN MODE] Messages will be generated and printed — nothing will be sent.")

    orchestrator = SequenceOrchestrator(db, settings, dry_run=dry_run)
    result = orchestrator.run_daily_session()

    click.echo(f"\nSession complete:")
    click.echo(f"  Connections sent:  {result.connections_sent}")
    click.echo(f"  Messages sent:     {result.messages_sent}")
    click.echo(f"  Replies detected:  {result.replies_detected}")
    click.echo(f"  Errors:            {result.errors}")
    if result.halted_early:
        click.echo(f"  [!] Session halted early: {result.halt_reason}")


@cli.command("import")
@click.option("--file", "filepath", required=True, help="Path to the CSV file with lead data.")
@click.option("--list-name", default=None, help="Optional label for this lead list (e.g. 'Q2 ICPs').")
def import_leads(filepath: str, list_name: str):
    """Import leads from a CSV file exported from Sales Navigator or any CRM."""
    from config.settings import load_settings
    from database.db import Database
    from outreach.importer import import_from_csv

    settings = load_settings()
    db = Database(settings.db_path)
    db.initialize_schema()

    click.echo(f"Importing leads from: {filepath}")
    result = import_from_csv(filepath, db, source_list=list_name)

    click.echo(f"  Added:   {result.added}")
    click.echo(f"  Skipped: {result.skipped} (duplicates or invalid)")
    if result.errors:
        click.echo(f"  Errors:  {len(result.errors)}")
        for err in result.errors[:10]:
            click.echo(f"    - {err}")


@cli.command()
def status():
    """Show a dashboard of your outreach pipeline and today's stats."""
    from config.settings import load_settings
    from database.db import Database
    from cli.dashboard import render_dashboard

    settings = load_settings()
    db = Database(settings.db_path)
    db.initialize_schema()
    render_dashboard(db)


@cli.command("mark-booked")
@click.option("--url", required=True, help="LinkedIn profile URL of the lead who booked a call.")
@click.option("--notes", default=None, help="Optional notes about the booking.")
def mark_booked(url: str, notes: str):
    """Manually mark a lead as having booked a discovery call."""
    from config.settings import load_settings
    from database.db import Database
    from database.queries import get_lead_by_url, mark_lead_booked, increment_daily_stat
    from datetime import date

    settings = load_settings()
    db = Database(settings.db_path)
    db.initialize_schema()

    with db.transaction() as conn:
        lead = get_lead_by_url(conn, url)
        if not lead:
            click.echo(f"Lead not found in database: {url}")
            return
        mark_lead_booked(conn, lead.id)
        if notes:
            conn.execute("UPDATE leads SET notes = ? WHERE id = ?", (notes, lead.id))
        increment_daily_stat(conn, date.today().isoformat(), "bookings_detected")

    name = lead.full_name or lead.first_name or url
    click.echo(f"Marked {name} as booked.")


@cli.command("mark-dnc")
@click.option("--url", required=True, help="LinkedIn profile URL to add to do-not-contact list.")
def mark_dnc(url: str):
    """Mark a lead as do-not-contact (stops all future outreach)."""
    from config.settings import load_settings
    from database.db import Database
    from database.queries import get_lead_by_url, update_lead_status

    settings = load_settings()
    db = Database(settings.db_path)

    with db.transaction() as conn:
        lead = get_lead_by_url(conn, url)
        if not lead:
            click.echo(f"Lead not found: {url}")
            return
        update_lead_status(conn, lead.id, "do_not_contact")

    click.echo(f"Marked {lead.full_name or url} as do-not-contact.")


if __name__ == "__main__":
    cli()
