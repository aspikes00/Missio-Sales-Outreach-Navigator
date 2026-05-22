from __future__ import annotations
import logging
import time
import random

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"

_CHECKPOINT_FRAGMENTS = ("/checkpoint/", "/challenge/", "/two-step/", "/verification/")
_FEED_FRAGMENTS = ("/feed", "/mynetwork", "/messaging", "/notifications", "/jobs", "/sales/")


class AuthError(Exception):
    pass


def _on_feed(url: str) -> bool:
    return any(f in url for f in _FEED_FRAGMENTS)


def _on_checkpoint(url: str) -> bool:
    return any(f in url for f in _CHECKPOINT_FRAGMENTS)


def _wait_for_verification(page: Page):
    print("\n" + "="*60)
    print("  LinkedIn needs verification.")
    print("  Complete it in the browser window — you have 2 minutes.")
    print("="*60 + "\n")
    page.wait_for_url("**linkedin.com/**", timeout=120000)
    time.sleep(2)
    if not _on_feed(page.url):
        raise AuthError(f"Verification did not land on feed. URL: {page.url}")
    logger.info("Verification complete. Logged in.")


def ensure_authenticated(page: Page, email: str, password: str):
    """Navigate to LinkedIn and ensure the session is authenticated, handling 2FA if needed."""
    logger.info("Checking LinkedIn session...")
    try:
        page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=25000)
    except Exception:
        pass

    time.sleep(random.uniform(2.0, 3.0))
    current_url = page.url
    logger.info("After feed navigation, URL: %s", current_url)

    if _on_feed(current_url):
        logger.info("Using existing LinkedIn session.")
        return

    if _on_checkpoint(current_url):
        _wait_for_verification(page)
        return

    # Not on feed and not on checkpoint — need to log in from scratch
    _do_login(page, email, password)


def _do_login(page: Page, email: str, password: str):
    logger.info("Logging in to LinkedIn...")
    page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded", timeout=20000)
    time.sleep(random.uniform(1.5, 3.0))

    current_url = page.url
    # LinkedIn may redirect away from /login if cookies are present
    if _on_feed(current_url):
        logger.info("Session active — redirected from login to feed.")
        return
    if _on_checkpoint(current_url):
        _wait_for_verification(page)
        return

    try:
        page.wait_for_selector(sel.LOGIN_EMAIL_INPUT, timeout=12000)
    except PWTimeout:
        # One final URL check before giving up
        current_url = page.url
        if _on_feed(current_url):
            logger.info("Session active.")
            return
        if _on_checkpoint(current_url):
            _wait_for_verification(page)
            return
        raise AuthError(
            f"Could not find login form (URL: {current_url}). "
            "LinkedIn may be showing an unexpected page."
        )

    _human_type(page, sel.LOGIN_EMAIL_INPUT, email)
    time.sleep(random.uniform(0.5, 1.5))
    _human_type(page, sel.LOGIN_PASSWORD_INPUT, password)
    time.sleep(random.uniform(0.8, 1.8))
    page.click(sel.LOGIN_SUBMIT_BUTTON)

    time.sleep(3)
    current_url = page.url
    if _on_checkpoint(current_url):
        print("\n" + "="*60)
        print("  LinkedIn is asking for a verification code.")
        print("  Check your phone/email, enter it in the browser,")
        print("  then click Sign in. You have 2 minutes.")
        print("="*60 + "\n")
        page.wait_for_url("**linkedin.com/**", timeout=120000)
        time.sleep(2)

    if not _on_feed(page.url):
        if page.query_selector(sel.CAPTCHA_INDICATOR):
            raise AuthError("CAPTCHA detected. Please log in manually and re-run.")
        if page.query_selector(sel.LOGIN_ERROR_BANNER):
            raise AuthError("Login failed — check LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env.")
        raise AuthError(f"Login timed out. Final URL: {page.url}")

    logger.info("Login successful.")


def _human_type(page: Page, selector: str, text: str):
    page.click(selector)
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.04, 0.14))
