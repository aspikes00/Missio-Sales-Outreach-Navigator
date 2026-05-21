import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime

import pytz

from ai.generator import MessageGenerator
from config.settings import Settings
from database.db import Database
from database.models import Lead
from database.queries import (
    get_leads_due_for_outreach,
    get_or_create_daily_stats,
    get_outreach_history,
    increment_daily_stat,
    insert_outreach_log,
    mark_lead_needs_response,
    update_lead_profile,
    update_lead_status,
    url_exists,
)
from linkedin.auth import ensure_authenticated
from linkedin.browser import BrowserManager
from linkedin.messenger import MessengerError, scan_inbox_for_replies, send_connection_request, send_direct_message
from linkedin.scraper import check_connection_accepted, scrape_profile
from outreach.scheduler import Scheduler
from safety.humanizer import Humanizer
from safety.watchdog import Watchdog, WatchdogStatus

logger = logging.getLogger(__name__)

# Maps a lead status to the next stage name and the new status after sending
STAGE_TRANSITIONS = {
    "not_contacted":       ("connection_note", "connection_pending"),
    "connection_pending":  None,  # handled separately (check if accepted)
    "connected":           ("message_1", "stage_1_sent"),
    "stage_1_sent":        ("message_2", "stage_2_sent"),
    "stage_2_sent":        ("message_3", "stage_3_sent"),
    "stage_3_sent":        (None, "not_interested"),  # just expire
}

TEMPLATE_FOR_STAGE = {
    "connection_note": "connection_note.txt",
    "message_1": "message_1.txt",
    "message_2": "message_2.txt",
    "message_3": "message_3.txt",
}


@dataclass
class SessionResult:
    connections_sent: int = 0
    messages_sent: int = 0
    replies_detected: int = 0
    errors: int = 0
    halted_early: bool = False
    halt_reason: str = ""
    leads_processed: list[str] = field(default_factory=list)


class SequenceOrchestrator:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        dry_run: bool = False,
    ):
        self._db = db
        self._settings = settings
        self._dry_run = dry_run
        self._generator = MessageGenerator(settings.anthropic_api_key, settings.anthropic_model)
        self._humanizer = Humanizer(settings.min_delay_seconds, settings.max_delay_seconds)
        self._watchdog = Watchdog(settings.max_consecutive_errors)
        self._scheduler = Scheduler(
            settings.daily_connection_limit,
            settings.daily_message_limit,
            settings.session_warmup_days,
        )

    def run_daily_session(self) -> SessionResult:
        result = SessionResult()
        today = date.today().isoformat()

        if not self._within_business_hours():
            logger.info("Outside business hours. Exiting.")
            result.halt_reason = "outside_business_hours"
            return result

        queue = self._scheduler.build_queue(self._db, today)
        if not queue:
            logger.info("Nothing to do today.")
            return result

        with BrowserManager(self._settings) as browser:
            ensure_authenticated(browser.page, self._settings.linkedin_email, self._settings.linkedin_password)

            # Scan inbox for replies before sending anything
            active_urls = self._get_active_lead_urls()
            replied_urls = scan_inbox_for_replies(browser.page, active_urls)
            if replied_urls:
                self._mark_replies(replied_urls, today)
                result.replies_detected = len(replied_urls)
                logger.info("%d replies detected and marked.", result.replies_detected)

            # Check connection_pending leads
            self._check_pending_connections(browser, today)

            for lead in queue:
                status = self._watchdog.check(browser.page)
                if status != WatchdogStatus.OK:
                    result.halted_early = True
                    result.halt_reason = status.value
                    logger.warning("Session halted: %s", status.value)
                    break

                success = self._execute_action(browser, lead, today, result)
                if success:
                    self._watchdog.record_success()
                else:
                    self._watchdog.record_failure()
                    result.errors += 1

                if not self._dry_run:
                    self._humanizer.between_action_delay()

        logger.info(
            "Session complete — connections: %d, messages: %d, replies: %d, errors: %d",
            result.connections_sent, result.messages_sent, result.replies_detected, result.errors,
        )
        return result

    def _execute_action(self, browser: BrowserManager, lead: Lead, today: str, result: SessionResult) -> bool:
        transition = STAGE_TRANSITIONS.get(lead.status)
        if transition is None:
            logger.debug("Lead %s (%s) has no action for status %s", lead.id, lead.linkedin_url, lead.status)
            return True

        stage_name, next_status = transition

        if stage_name is None:
            # Expire the lead (e.g., stage_3_sent → not_interested)
            with self._db.transaction() as conn:
                update_lead_status(conn, lead.id, next_status)
            return True

        template = self._settings.load_template(TEMPLATE_FOR_STAGE[stage_name])
        history = self._get_prior_messages(lead.id)

        # Refresh profile data before generating for deep personalization
        try:
            profile = scrape_profile(browser.page, lead.linkedin_url)
            if profile:
                with self._db.transaction() as conn:
                    update_lead_profile(
                        conn, lead.id,
                        headline=profile.headline,
                        about_snippet=profile.about_snippet,
                        recent_post_1=profile.recent_posts[0] if len(profile.recent_posts) > 0 else None,
                        recent_post_2=profile.recent_posts[1] if len(profile.recent_posts) > 1 else None,
                        recent_post_3=profile.recent_posts[2] if len(profile.recent_posts) > 2 else None,
                        connection_degree=profile.connection_degree,
                    )
                    lead.headline = profile.headline
                    lead.about_snippet = profile.about_snippet
                    if profile.recent_posts:
                        lead.recent_post_1 = profile.recent_posts[0] if len(profile.recent_posts) > 0 else None
                        lead.recent_post_2 = profile.recent_posts[1] if len(profile.recent_posts) > 1 else None
                        lead.recent_post_3 = profile.recent_posts[2] if len(profile.recent_posts) > 2 else None
        except Exception as e:
            logger.warning("Profile refresh failed for %s: %s", lead.linkedin_url, e)

        message = self._generator.generate(
            lead=lead,
            stage=stage_name,
            template=template,
            calendly_link=self._settings.calendly_link,
            prior_messages=history,
        )

        if self._dry_run:
            logger.info(
                "[DRY RUN] Would send %s to %s:\n%s",
                stage_name, lead.full_name or lead.first_name, message,
            )
            print(f"\n{'='*60}")
            print(f"STAGE: {stage_name} | LEAD: {lead.full_name or lead.first_name} @ {lead.company_name}")
            print(f"{'='*60}")
            print(message)
            print(f"{'='*60}\n")
            return True

        try:
            if stage_name == "connection_note":
                sent = send_connection_request(browser.page, lead.linkedin_url, message, self._humanizer)
                if sent:
                    result.connections_sent += 1
            else:
                sent = send_direct_message(browser.page, lead.linkedin_url, message, self._humanizer)
                if sent:
                    result.messages_sent += 1

            if sent:
                with self._db.transaction() as conn:
                    insert_outreach_log(conn, lead.id, stage_name, message)
                    update_lead_status(conn, lead.id, next_status)
                    field = "connections_sent" if stage_name == "connection_note" else "messages_sent"
                    increment_daily_stat(conn, today, field)
                result.leads_processed.append(lead.linkedin_url)
                return True
            return False

        except MessengerError as e:
            logger.error("Messenger error for %s: %s", lead.linkedin_url, e)
            with self._db.transaction() as conn:
                insert_outreach_log(conn, lead.id, stage_name, message, status="failed", error_message=str(e))
                increment_daily_stat(conn, today, "errors_encountered")
            return False
        except Exception as e:
            logger.error("Unexpected error for %s: %s", lead.linkedin_url, e)
            return False

    def _check_pending_connections(self, browser: BrowserManager, today: str):
        from database.queries import STAGE_WAIT_DAYS, get_leads_due_for_outreach
        from datetime import datetime, timedelta

        cutoff_days = STAGE_WAIT_DAYS["connection_pending"]
        cutoff = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

        with self._db.transaction() as conn:
            from database.queries import get_lead_by_id
            cur = conn.execute(
                "SELECT * FROM leads WHERE status = 'connection_pending' LIMIT 20"
            )
            pending = [Lead.from_row(tuple(r)) for r in cur.fetchall()]

        for lead in pending:
            try:
                accepted = check_connection_accepted(browser.page, lead.linkedin_url)
                if accepted:
                    with self._db.transaction() as conn:
                        update_lead_status(conn, lead.id, "connected")
                    logger.info("%s accepted the connection request.", lead.full_name or lead.first_name)
                    self._humanizer.human_delay(2, 5)
            except Exception as e:
                logger.warning("Could not check pending for %s: %s", lead.linkedin_url, e)

    def _mark_replies(self, replied_urls: list[str], today: str):
        for url in replied_urls:
            with self._db.transaction() as conn:
                from database.queries import get_lead_by_url
                lead = get_lead_by_url(conn, url)
                if lead:
                    mark_lead_needs_response(conn, lead.id)
                    increment_daily_stat(conn, today, "replies_received")

    def _get_active_lead_urls(self) -> list[str]:
        active_statuses = ("stage_1_sent", "stage_2_sent", "stage_3_sent", "connected")
        urls = []
        with self._db.transaction() as conn:
            for status in active_statuses:
                rows = conn.execute(
                    "SELECT linkedin_url FROM leads WHERE status = ?", (status,)
                ).fetchall()
                urls.extend(row[0] for row in rows)
        return urls

    def _get_prior_messages(self, lead_id: int) -> list[str]:
        with self._db.transaction() as conn:
            history = get_outreach_history(conn, lead_id)
        return [entry.message_text for entry in history]

    def _within_business_hours(self) -> bool:
        tz = pytz.timezone(self._settings.timezone)
        now = datetime.now(tz)
        return self._settings.business_hours_start <= now.hour < self._settings.business_hours_end
