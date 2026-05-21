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


def is_logged_in(page: Page) -> bool:
    try:
        page.goto(LINKEDIN_FEED_URL, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_selector(sel.FEED_NAV, timeout=8000)
        return True
    except (PWTimeout, Exception):
        return False


def login(page: Page, email: str, password: str) -> bool:
    logger.info("Logging in to LinkedIn...")
    page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded")
    time.sleep(random.uniform(1.5, 3.0))

    try:
        email_input = page.wait_for_selector(sel.LOGIN_EMAIL_INPUT, timeout=10000)
        _human_type(page, sel.LOGIN_EMAIL_INPUT, email)
        time.sleep(random.uniform(0.5, 1.5))

        _human_type(page, sel.LOGIN_PASSWORD_INPUT, password)
        time.sleep(random.uniform(0.8, 1.8))

        page.click(sel.LOGIN_SUBMIT_BUTTON)
        page.wait_for_url("**/feed/**", timeout=20000)
        logger.info("Login successful.")
        return True

    except PWTimeout:
        if page.query_selector(sel.CAPTCHA_INDICATOR):
            raise AuthError("CAPTCHA detected during login. Please log in manually and re-run.")
        if page.query_selector(sel.LOGIN_ERROR_BANNER):
            raise AuthError("LinkedIn login failed — check your LINKEDIN_EMAIL and LINKEDIN_PASSWORD.")
        raise AuthError("Login timed out. LinkedIn may be slow or the page layout changed.")


def ensure_authenticated(page: Page, email: str, password: str):
    if is_logged_in(page):
        logger.info("Using existing LinkedIn session.")
        return
    login(page, email, password)


def _human_type(page: Page, selector: str, text: str):
    page.click(selector)
    for char in text:
        page.keyboard.type(char)
        time.sleep(random.uniform(0.04, 0.14))
