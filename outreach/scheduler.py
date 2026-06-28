from __future__ import annotations
import logging
import random

from database.db import Database
from database.models import Lead
from database.queries import (
    get_active_days_count,
    get_leads_due_for_outreach,
    get_message_due_leads,
    get_not_contacted_leads,
    get_or_create_daily_stats,
)

logger = logging.getLogger(__name__)

WARMUP_SCHEDULE = [
    (2, 5),   # Days 1-2:  5 actions/day
    (4, 10),  # Days 3-4: 10 actions/day
    (6, 15),  # Days 5-6: 15 actions/day
    (7, 20),  # Day 7:    20 actions/day → ramp complete
]


class Scheduler:
    def __init__(self, daily_connection_limit: int, daily_message_limit: int, warmup_days: int):
        self._connection_limit = daily_connection_limit
        self._message_limit = daily_message_limit
        self._warmup_days = warmup_days

    def build_queue(self, db: Database, today: str, brand: str) -> list[Lead]:
        with db.transaction() as conn:
            stats = get_or_create_daily_stats(conn, today, brand)
            active_days = get_active_days_count(conn, brand)

        effective_limit = self._get_effective_limit(active_days)
        remaining = effective_limit - stats.total_sent
        if remaining <= 0:
            logger.info("[%s] Daily limit reached (%d actions). No more sends today.", brand, effective_limit)
            return []

        in_warmup = active_days <= self._warmup_days

        if in_warmup:
            # During warmup connections and messages share a single pool
            with db.transaction() as conn:
                candidates = get_leads_due_for_outreach(conn, today, limit=remaining * 3, brand=brand)
            if not candidates:
                logger.info("[%s] No leads due for outreach today.", brand)
                return []
            random.shuffle(candidates)
            queue = candidates[:remaining]
        else:
            # Post-warmup: reserve dedicated slots for connections and messages so neither
            # starves the other. Previously a shuffled combined pool let message-due leads
            # crowd out not_contacted leads, causing only 3 connections per day.
            conn_remaining = max(0, self._connection_limit - stats.connections_sent)
            msg_remaining = max(0, self._message_limit - stats.messages_sent)

            with db.transaction() as conn:
                conn_leads = get_not_contacted_leads(conn, brand, limit=conn_remaining)
                msg_leads = get_message_due_leads(conn, today, brand, limit=msg_remaining)

            random.shuffle(conn_leads)
            random.shuffle(msg_leads)
            queue = conn_leads[:conn_remaining] + msg_leads[:msg_remaining]
            random.shuffle(queue)

            if not queue:
                logger.info("[%s] No leads due for outreach today.", brand)
                return []

        conn_count = sum(1 for l in queue if l.status == "not_contacted")
        msg_count = len(queue) - conn_count
        logger.info(
            "[%s] Queue built: %d leads (%d connections, %d messages, effective limit: %d, already sent: %d)",
            brand, len(queue), conn_count, msg_count, effective_limit, stats.total_sent,
        )
        return queue

    def _get_effective_limit(self, active_days: int) -> int:
        if active_days <= self._warmup_days:
            for threshold, limit in WARMUP_SCHEDULE:
                if active_days <= threshold:
                    logger.info("Warmup mode (day %d): limit is %d/day", active_days, limit)
                    return limit
        return self._connection_limit + self._message_limit

    def connections_remaining(self, db: Database, today: str, brand: str) -> int:
        with db.transaction() as conn:
            stats = get_or_create_daily_stats(conn, today, brand)
        return max(0, self._connection_limit - stats.connections_sent)

    def messages_remaining(self, db: Database, today: str, brand: str) -> int:
        with db.transaction() as conn:
            stats = get_or_create_daily_stats(conn, today, brand)
        return max(0, self._message_limit - stats.messages_sent)
