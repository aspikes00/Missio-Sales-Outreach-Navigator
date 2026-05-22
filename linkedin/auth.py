from __future__ import annotations
import logging
import time
import random

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)

LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed/"


class AuthError(Exception):
    pass


def ensure_authenticated(page: Page, email: str, password: str):
    """Navigate to LinkedIn and ensure the session is authenticated, handling 2FA if needed."""
    logger.info("Checking LinkedIn session...")
    try:
        page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=20000)
    except Exception:
        pass

    time.sleep(random.uniform(2.0, 3.0))
    current_url = page.url

    # Already on feed — logged in
    if "/feed" in current_url:
        try:
            page.wait_for_selector(sel.FEED_NAV, timeout=10000)
            logger.info("Using existing LinkedIn session.")
            return
        except PWTimeout:
            pass

    # On a verification/checkpoint page — wait for user to complete it
    if any(x in current_url for x in ("/checkpoint/", "/challenge/", "/two-step/", "/verification/")):
        print("\n" + "="*60)
        print("  LinkedIn needs additional verification.")
        print("  Complete it in the browser window.")
        print("  You have 2 minutes.")
        print("="*60 + "\n")
        page.wait_for_url("**/feed/**", timeout=120000)
        logger.info("Verification complete. Logged in.")
        return

    # Need a fresh login
    _do_login(page, email, password)


def _do_login(page: Page, email: str, password: str):
    logger.info("Logging in to LinkedIn...")
    page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded")
    time.sleep(random.uniform(1.5, 3.0))

    try:
        page.wait_for_selector(sel.LOGIN_EMAIL_INPUT, timeout=10000)
        _human_type(page, sel.LOGIN_EMAIL_INPUT, email)
        time.sleep(random.uniform(0.5, 1.5))

        _human_type(page, sel.LOGIN_PASSWORD_INPUT, password)
        time.sleep(random.uniform(0.8, 1.8))

        page.click(sel.LOGIN_SUBMIT_BUTTON)

        # Wait briefly then check if 2FA/verification is required
        time.sleep(3)
        current_url = page.url
        if any(x in current_url for x in ("/checkpoint/", "/challenge/", "/two-step/", "/verification/")):
            print("\n" + "="*60)
            print("  LinkedIn is asking for a verification code.")
            print("  Check your phone/email for the code, enter it in")
            print("  the browser window, then click 'Sign in'.")
            print("  You have 2 minutes.")
            print("="*60 + "\n")
            page.wait_for_url("**/feed/**", timeout=120000)
        else:
            page.wait_for_url("**/feed/**", timeout=20000)

        logger.info("Login successful.")

    except PWTimeout:
        if page.query_selector(sel.CAPTCHA_INDICATOR):
            raise AuthError("CAPTCHA detected during login. Please log in manually and re-run.")
        if page.query_selector(sel.LOGIN_ERROR_BANNER):
            raise AuthError("LinkedIn login failed — check your LINKEDIN_EMAIL and LINKEDIN_PASSWORD.")
        raise AuthError("Login timed out. LinkedIn may be slow or the page layout changed.")


def _human_type(page: Page, selector: str, text: str):
    page.click(selector)
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.04, 0.14))
