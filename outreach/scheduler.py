import logging
import random
from datetime import date

from database.db import Database
from database.models import Lead
from database.queries import (
    get_active_days_count,
    get_leads_due_for_outreach,
    get_or_create_daily_stats,
)

logger = logging.getLogger(__name__)

WARMUP_SCHEDULE = [
    (3, 3),   # days 1-3: max 3/day
    (7, 5),   # days 4-7: max 5/day
]


class Scheduler:
    def __init__(self, daily_connection_limit: int, daily_message_limit: int, warmup_days: int):
        self._connection_limit = daily_connection_limit
        self._message_limit = daily_message_limit
        self._warmup_days = warmup_days

    def build_queue(self, db: Database, today: str) -> list[Lead]:
        with db.transaction() as conn:
            stats = get_or_create_daily_stats(conn, today)
            active_days = get_active_days_count(conn)

        effective_limit = self._get_effective_limit(active_days)
        remaining = effective_limit - stats.total_sent
        if remaining <= 0:
            logger.info("Daily limit already reached (%d actions). No more sends today.", effective_limit)
            return []

        with db.transaction() as conn:
            candidates = get_leads_due_for_outreach(conn, today, limit=remaining * 3)

        if not candidates:
            logger.info("No leads due for outreach today.")
            return []

        random.shuffle(candidates)
        queue = candidates[:remaining]
        logger.info(
            "Queue built: %d leads (effective daily limit: %d, already sent: %d)",
            len(queue), effective_limit, stats.total_sent,
        )
        return queue

    def _get_effective_limit(self, active_days: int) -> int:
        if active_days <= self._warmup_days:
            for threshold, limit in WARMUP_SCHEDULE:
                if active_days <= threshold:
                    logger.info("Warmup mode (day %d): limit is %d/day", active_days, limit)
                    return limit
        total = self._connection_limit + self._message_limit
        return total

    def connections_remaining(self, db: Database, today: str) -> int:
        with db.transaction() as conn:
            stats = get_or_create_daily_stats(conn, today)
        return max(0, self._connection_limit - stats.connections_sent)

    def messages_remaining(self, db: Database, today: str) -> int:
        with db.transaction() as conn:
            stats = get_or_create_daily_stats(conn, today)
        return max(0, self._message_limit - stats.messages_sent)
