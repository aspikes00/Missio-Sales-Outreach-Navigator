import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime

import pytz

from ai.generator import MessageGenerator
from config.settings import BrandConfig, Settings
from database.db import Database
from database.models import Lead
from database.queries import (
    get_active_lead_urls_for_brand,
    get_lead_by_url,
    get_or_create_daily_stats,
    get_outreach_history,
    increment_daily_stat,
    insert_outreach_log,
    mark_lead_needs_response,
    update_lead_profile,
    update_lead_status,
)
from linkedin.auth import ensure_authenticated
from linkedin.browser import BrowserManager
from linkedin.messenger import MessengerError, scan_inbox_for_replies, send_connection_request, send_direct_message
from linkedin.scraper import check_connection_accepted, scrape_profile
from outreach.scheduler import Scheduler
from safety.humanizer import Humanizer
from safety.watchdog import Watchdog, WatchdogStatus

logger = logging.getLogger(__name__)

STAGE_TRANSITIONS = {
    "not_contacted":      ("connection_note", "connection_pending"),
    "connection_pending": None,
    "connected":          ("message_1", "stage_1_sent"),
    "stage_1_sent":       ("message_2", "stage_2_sent"),
    "stage_2_sent":       ("message_3", "stage_3_sent"),
    "stage_3_sent":       (None, "not_interested"),
}

TEMPLATE_FOR_STAGE = {
    "connection_note": "connection_note.txt",
    "message_1":       "message_1.txt",
    "message_2":       "message_2.txt",
    "message_3":       "message_3.txt",
}


@dataclass
class SessionResult:
    brand: str = ""
    connections_sent: int = 0
    messages_sent: int = 0
    replies_detected: int = 0
    errors: int = 0
    halted_early: bool = False
    halt_reason: str = ""
    leads_processed: list[str] = field(default_factory=list)


class SequenceOrchestrator:
    def __init__(self, db: Database, settings: Settings, brand: BrandConfig, dry_run: bool = False):
        self._db = db
        self._settings = settings
        self._brand = brand
        self._dry_run = dry_run
        self._generator = MessageGenerator(settings.anthropic_api_key, settings.anthropic_model)
        self._humanizer = Humanizer(settings.min_delay_seconds, settings.max_delay_seconds)
        self._watchdog = Watchdog(settings.max_consecutive_errors)
        self._scheduler = Scheduler(
            brand.daily_connection_limit,
            brand.daily_message_limit,
            settings.session_warmup_days,
        )

    def run_daily_session(self) -> SessionResult:
        result = SessionResult(brand=self._brand.slug)
        today = date.today().isoformat()

        if not self._within_business_hours():
            logger.info("Outside business hours. Exiting.")
            result.halt_reason = "outside_business_hours"
            return result

        queue = self._scheduler.build_queue(self._db, today, self._brand.slug)
        if not queue:
            return result

        with BrowserManager(self._settings) as browser:
            ensure_authenticated(
                browser.page, self._settings.linkedin_email, self._settings.linkedin_password
            )

            # Scan inbox for replies
            with self._db.transaction() as conn:
                active_urls = get_active_lead_urls_for_brand(conn, self._brand.slug)
            replied_urls = scan_inbox_for_replies(browser.page, active_urls)
            if replied_urls:
                self._mark_replies(replied_urls, today)
                result.replies_detected = len(replied_urls)

            # Check pending connection requests
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
            "[%s] Session complete — connections: %d, messages: %d, replies: %d, errors: %d",
            self._brand.slug, result.connections_sent, result.messages_sent,
            result.replies_detected, result.errors,
        )
        return result

    def _execute_action(
        self, browser: BrowserManager, lead: Lead, today: str, result: SessionResult
    ) -> bool:
        transition = STAGE_TRANSITIONS.get(lead.status)
        if transition is None:
            return True

        stage_name, next_status = transition

        if stage_name is None:
            with self._db.transaction() as conn:
                update_lead_status(conn, lead.id, next_status)
            return True

        template = self._brand.load_template(TEMPLATE_FOR_STAGE[stage_name])
        history = self._get_prior_messages(lead.id)

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
                lead.recent_post_1 = profile.recent_posts[0] if len(profile.recent_posts) > 0 else None
                lead.recent_post_2 = profile.recent_posts[1] if len(profile.recent_posts) > 1 else None
                lead.recent_post_3 = profile.recent_posts[2] if len(profile.recent_posts) > 2 else None
        except Exception as e:
            logger.warning("Profile refresh failed for %s: %s", lead.linkedin_url, e)

        message = self._generator.generate(
            lead=lead,
            stage=stage_name,
            template=template,
            brand=self._brand,
            prior_messages=history,
        )

        if self._dry_run:
            print(f"\n{'='*60}")
            print(f"BRAND: {self._brand.name} | STAGE: {stage_name}")
            print(f"LEAD: {lead.full_name or lead.first_name} @ {lead.company_name}")
            print(f"{'='*60}")
            print(message)
            print(f"{'='*60}\n")
            return True

        try:
            sent = False
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
                    insert_outreach_log(conn, lead.id, self._brand.slug, stage_name, message)
                    update_lead_status(conn, lead.id, next_status)
                    stat_field = "connections_sent" if stage_name == "connection_note" else "messages_sent"
                    increment_daily_stat(conn, today, self._brand.slug, stat_field)
                result.leads_processed.append(lead.linkedin_url)
                return True
            return False

        except MessengerError as e:
            logger.error("Messenger error for %s: %s", lead.linkedin_url, e)
            with self._db.transaction() as conn:
                insert_outreach_log(
                    conn, lead.id, self._brand.slug, stage_name, message,
                    status="failed", error_message=str(e),
                )
                increment_daily_stat(conn, today, self._brand.slug, "errors_encountered")
            return False
        except Exception as e:
            logger.error("Unexpected error for %s: %s", lead.linkedin_url, e)
            return False

    def _check_pending_connections(self, browser: BrowserManager, today: str):
        with self._db.transaction() as conn:
            cur = conn.execute(
                "SELECT * FROM leads WHERE brand = ? AND status = 'connection_pending' LIMIT 20",
                (self._brand.slug,),
            )
            pending = [Lead.from_row(tuple(r)) for r in cur.fetchall()]

        for lead in pending:
            try:
                accepted = check_connection_accepted(browser.page, lead.linkedin_url)
                if accepted:
                    with self._db.transaction() as conn:
                        update_lead_status(conn, lead.id, "connected")
                    logger.info("%s accepted the connection.", lead.full_name or lead.first_name)
                    self._humanizer.human_delay(2, 5)
            except Exception as e:
                logger.warning("Could not check pending for %s: %s", lead.linkedin_url, e)

    def _mark_replies(self, replied_urls: list[str], today: str):
        for url in replied_urls:
            with self._db.transaction() as conn:
                lead = get_lead_by_url(conn, url)
                if lead:
                    mark_lead_needs_response(conn, lead.id)
                    increment_daily_stat(conn, today, self._brand.slug, "replies_received")

    def _get_prior_messages(self, lead_id: int) -> list[str]:
        with self._db.transaction() as conn:
            history = get_outreach_history(conn, lead_id)
        return [entry.message_text for entry in history]

    def _within_business_hours(self) -> bool:
        tz = pytz.timezone(self._settings.timezone)
        now = datetime.now(tz)
        return self._settings.business_hours_start <= now.hour < self._settings.business_hours_end
