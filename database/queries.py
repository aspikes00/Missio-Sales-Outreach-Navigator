from __future__ import annotations
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from database.models import DailyStats, Lead, OutreachLog

# Days to wait between each stage touch
STAGE_WAIT_DAYS = {
    "connected":          0,   # message_1 same day connection accepted
    "stage_1_sent":       3,   # message_2 at day 3
    "stage_2_sent":       3,   # message_3 at day 6
    "stage_3_sent":       5,   # message_4 at day 11
    "stage_4_sent":       5,   # message_5 at day 16
    "stage_5_sent":       7,   # mark not_interested at day 23
    "connection_pending": 21,
}


def get_leads_due_for_outreach(
    conn: sqlite3.Connection, today: str, limit: int, brand: str
) -> list[Lead]:
    rows = []
    for status, wait_days in STAGE_WAIT_DAYS.items():
        cutoff = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=wait_days)).strftime("%Y-%m-%d")
        cur = conn.execute(
            """
            SELECT * FROM leads
            WHERE brand = ? AND status = ?
              AND (last_activity_at IS NULL OR date(last_activity_at) <= ?)
            ORDER BY last_activity_at ASC
            LIMIT ?
            """,
            (brand, status, cutoff, limit - len(rows)),
        )
        rows.extend(cur.fetchall())
        if len(rows) >= limit:
            break

    not_contacted = conn.execute(
        "SELECT * FROM leads WHERE brand = ? AND status = 'not_contacted' ORDER BY id DESC LIMIT ?",
        (brand, max(0, limit - len(rows))),
    ).fetchall()
    rows.extend(not_contacted)

    return [Lead.from_row(tuple(r)) for r in rows[:limit]]


def get_not_contacted_leads(conn: sqlite3.Connection, brand: str, limit: int) -> list[Lead]:
    """Leads ready for a first connection request."""
    rows = conn.execute(
        "SELECT * FROM leads WHERE brand = ? AND status = 'not_contacted' ORDER BY id DESC LIMIT ?",
        (brand, limit),
    ).fetchall()
    return [Lead.from_row(tuple(r)) for r in rows]


def get_message_due_leads(conn: sqlite3.Connection, today: str, brand: str, limit: int) -> list[Lead]:
    """Leads due for a follow-up message (connected or stage_1-5_sent, past their wait period)."""
    message_statuses = {
        k: v for k, v in STAGE_WAIT_DAYS.items()
        if k not in ("connection_pending",)
    }
    rows = []
    for status, wait_days in message_statuses.items():
        if len(rows) >= limit:
            break
        cutoff = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=wait_days)).strftime("%Y-%m-%d")
        cur = conn.execute(
            """
            SELECT * FROM leads
            WHERE brand = ? AND status = ?
              AND (last_activity_at IS NULL OR date(last_activity_at) <= ?)
            ORDER BY last_activity_at ASC
            LIMIT ?
            """,
            (brand, status, cutoff, limit - len(rows)),
        )
        rows.extend(cur.fetchall())
    return [Lead.from_row(tuple(r)) for r in rows[:limit]]


def get_lead_by_url(conn: sqlite3.Connection, linkedin_url: str) -> Optional[Lead]:
    row = conn.execute("SELECT * FROM leads WHERE linkedin_url = ?", (linkedin_url,)).fetchone()
    return Lead.from_row(tuple(row)) if row else None


def get_lead_by_id(conn: sqlite3.Connection, lead_id: int) -> Optional[Lead]:
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return Lead.from_row(tuple(row)) if row else None


def insert_lead(conn: sqlite3.Connection, lead: Lead) -> int:
    cur = conn.execute(
        """
        INSERT INTO leads (
            linkedin_url, brand, first_name, last_name, full_name, title,
            company_name, industry, location, headline, about_snippet,
            recent_post_1, recent_post_2, recent_post_3,
            connection_degree, status, source_list
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead.linkedin_url, lead.brand, lead.first_name, lead.last_name, lead.full_name,
            lead.title, lead.company_name, lead.industry, lead.location,
            lead.headline, lead.about_snippet,
            lead.recent_post_1, lead.recent_post_2, lead.recent_post_3,
            lead.connection_degree, lead.status, lead.source_list,
        ),
    )
    return cur.lastrowid


def update_lead_status(conn: sqlite3.Connection, lead_id: int, status: str):
    conn.execute(
        "UPDATE leads SET status = ?, last_activity_at = ? WHERE id = ?",
        (status, datetime.utcnow().isoformat(), lead_id),
    )


def update_lead_profile(conn: sqlite3.Connection, lead_id: int, **fields):
    allowed = {
        "headline", "about_snippet", "recent_post_1", "recent_post_2",
        "recent_post_3", "connection_degree", "title", "company_name",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(
        f"UPDATE leads SET {set_clause} WHERE id = ?",
        (*updates.values(), lead_id),
    )


def mark_lead_needs_response(conn: sqlite3.Connection, lead_id: int):
    conn.execute(
        "UPDATE leads SET status = 'needs_response', last_activity_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), lead_id),
    )


def mark_lead_booked(conn: sqlite3.Connection, lead_id: int):
    conn.execute(
        "UPDATE leads SET status = 'booked', calendly_booked = 1, last_activity_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), lead_id),
    )


def insert_outreach_log(
    conn: sqlite3.Connection,
    lead_id: int,
    brand: str,
    stage: str,
    message_text: str,
    status: str = "sent",
    error_message: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO outreach_log (lead_id, brand, stage, message_text, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (lead_id, brand, stage, message_text, status, error_message),
    )
    return cur.lastrowid


def get_outreach_history(conn: sqlite3.Connection, lead_id: int) -> list[OutreachLog]:
    rows = conn.execute(
        "SELECT * FROM outreach_log WHERE lead_id = ? ORDER BY sent_at ASC",
        (lead_id,),
    ).fetchall()
    return [OutreachLog.from_row(tuple(r)) for r in rows]


def get_or_create_daily_stats(conn: sqlite3.Connection, today: str, brand: str) -> DailyStats:
    row = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ? AND brand = ?", (today, brand)
    ).fetchone()
    if row:
        return DailyStats.from_row(tuple(row))
    conn.execute(
        "INSERT OR IGNORE INTO daily_stats (date, brand) VALUES (?, ?)", (today, brand)
    )
    row = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ? AND brand = ?", (today, brand)
    ).fetchone()
    return DailyStats.from_row(tuple(row))


def get_daily_stats_range(
    conn: sqlite3.Connection, start_date: str, end_date: str, brand: Optional[str] = None
) -> list[DailyStats]:
    if brand:
        rows = conn.execute(
            "SELECT * FROM daily_stats WHERE date >= ? AND date <= ? AND brand = ? ORDER BY date ASC",
            (start_date, end_date, brand),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM daily_stats WHERE date >= ? AND date <= ? ORDER BY date, brand ASC",
            (start_date, end_date),
        ).fetchall()
    return [DailyStats.from_row(tuple(r)) for r in rows]


def get_all_brands_daily_stats(conn: sqlite3.Connection, today: str) -> list[DailyStats]:
    rows = conn.execute(
        "SELECT * FROM daily_stats WHERE date = ? ORDER BY brand ASC", (today,)
    ).fetchall()
    return [DailyStats.from_row(tuple(r)) for r in rows]


def increment_daily_stat(conn: sqlite3.Connection, today: str, brand: str, field: str, amount: int = 1):
    allowed = {
        "connections_sent", "messages_sent", "replies_received",
        "bookings_detected", "session_duration_mins", "errors_encountered", "inmails_sent",
    }
    if field not in allowed:
        raise ValueError(f"Unknown stat field: {field}")
    conn.execute(
        f"UPDATE daily_stats SET {field} = {field} + ? WHERE date = ? AND brand = ?",
        (amount, today, brand),
    )


def get_pipeline_counts(conn: sqlite3.Connection, brand: Optional[str] = None) -> dict[str, int]:
    if brand:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM leads WHERE brand = ? GROUP BY status ORDER BY status",
            (brand,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT status, COUNT(*) FROM leads GROUP BY status ORDER BY status"
        ).fetchall()
    return {row[0]: row[1] for row in rows}


def get_pipeline_by_brand(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    rows = conn.execute(
        "SELECT brand, status, COUNT(*) FROM leads GROUP BY brand, status ORDER BY brand, status"
    ).fetchall()
    result: dict[str, dict[str, int]] = {}
    for brand, status, count in rows:
        result.setdefault(brand, {})[status] = count
    return result


def get_active_days_count(conn: sqlite3.Connection, brand: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM daily_stats WHERE brand = ? AND connections_sent + messages_sent > 0",
        (brand,),
    ).fetchone()
    return row[0] if row else 0


def get_active_lead_urls_for_brand(conn: sqlite3.Connection, brand: str) -> list[str]:
    active_statuses = ("connected", "stage_1_sent", "stage_2_sent", "stage_3_sent", "stage_4_sent", "stage_5_sent")
    urls = []
    for status in active_statuses:
        rows = conn.execute(
            "SELECT linkedin_url FROM leads WHERE brand = ? AND status = ?", (brand, status)
        ).fetchall()
        urls.extend(row[0] for row in rows)
    return urls


def url_exists(conn: sqlite3.Connection, linkedin_url: str) -> bool:
    row = conn.execute("SELECT 1 FROM leads WHERE linkedin_url = ?", (linkedin_url,)).fetchone()
    return row is not None


def get_monthly_inmails_sent(conn: sqlite3.Connection, brand: str, year_month: str) -> int:
    """year_month format: '2026-05'"""
    row = conn.execute(
        "SELECT COALESCE(SUM(inmails_sent), 0) FROM daily_stats WHERE date LIKE ? AND brand = ?",
        (year_month + "%", brand),
    ).fetchone()
    return row[0] if row else 0
