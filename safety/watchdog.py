import logging
from enum import Enum

from playwright.sync_api import Page

from linkedin import selectors as sel

logger = logging.getLogger(__name__)


class WatchdogStatus(Enum):
    OK = "ok"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    SESSION_EXPIRED = "session_expired"
    CIRCUIT_OPEN = "circuit_open"


class Watchdog:
    def __init__(self, max_consecutive_errors: int = 3):
        self._max_errors = max_consecutive_errors
        self._consecutive_errors = 0

    def check(self, page: Page) -> WatchdogStatus:
        if self._consecutive_errors >= self._max_errors:
            logger.error("Circuit breaker open: %d consecutive errors.", self._consecutive_errors)
            return WatchdogStatus.CIRCUIT_OPEN

        if self._detect_captcha(page):
            logger.error(
                "CAPTCHA detected! Halting session. "
                "Please open LinkedIn manually, solve the CAPTCHA, and re-run."
            )
            return WatchdogStatus.CAPTCHA

        if self._detect_rate_limit(page):
            logger.warning("LinkedIn rate limit banner detected. Stopping for today.")
            return WatchdogStatus.RATE_LIMITED

        if self._detect_session_expired(page):
            logger.warning("Session appears expired — re-authentication needed.")
            return WatchdogStatus.SESSION_EXPIRED

        return WatchdogStatus.OK

    def record_success(self):
        self._consecutive_errors = 0

    def record_failure(self):
        self._consecutive_errors += 1
        logger.warning("Consecutive error count: %d / %d", self._consecutive_errors, self._max_errors)

    def _detect_captcha(self, page: Page) -> bool:
        try:
            return (
                page.query_selector(sel.CAPTCHA_INDICATOR) is not None
                or "challenge" in page.url
                or "checkpoint" in page.url
            )
        except Exception:
            return False

    def _detect_rate_limit(self, page: Page) -> bool:
        try:
            if page.query_selector(sel.RATE_LIMIT_BANNER):
                return True
            if page.query_selector(sel.GENERIC_ERROR_BANNER):
                return True
            content = page.content()
            return "weekly invitation limit" in content.lower() or "you've reached" in content.lower()
        except Exception:
            return False

    def _detect_session_expired(self, page: Page) -> bool:
        try:
            return "login" in page.url and "linkedin.com" in page.url
        except Exception:
            return False
