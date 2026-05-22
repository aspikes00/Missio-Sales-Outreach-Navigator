from __future__ import annotations
import logging
import time
import random

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)


def get_lead_urls_from_list(page: Page, list_url: str, max_leads: int = 200) -> list[str]:
    """Navigate a Sales Navigator saved lead list and return all profile URLs."""
    logger.info("Loading Sales Navigator list: %s", list_url)
    page.goto(list_url, wait_until="domcontentloaded")
    time.sleep(random.uniform(3.0, 5.0))

    urls: list[str] = []

    while len(urls) < max_leads:
        try:
            page.wait_for_selector(sel.SALES_NAV_LEAD_LIST_ITEM, timeout=15000)
        except PWTimeout:
            logger.warning("No lead list items found on page — list may be empty or selector changed.")
            break

        items = page.query_selector_all(sel.SALES_NAV_LEAD_LIST_ITEM)
        for item in items:
            href = item.get_attribute("href")
            if href and "/sales/lead/" in href:
                profile_url = _sales_to_public_url(href)
                if profile_url and profile_url not in urls:
                    urls.append(profile_url)

        logger.info("Collected %d lead URLs so far...", len(urls))

        next_btn = page.query_selector(sel.SALES_NAV_PAGINATION_NEXT)
        if not next_btn or next_btn.is_disabled():
            break

        next_btn.click()
        time.sleep(random.uniform(2.5, 4.5))

    logger.info("Total lead URLs collected: %d", len(urls))
    return urls[:max_leads]


def navigate_to_profile(page: Page, profile_url: str) -> bool:
    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(1.5, 3.0))
        return True
    except PWTimeout:
        logger.warning("Timeout navigating to %s", profile_url)
        return False


def _sales_to_public_url(sales_url: str) -> str | None:
    """
    Convert a Sales Navigator lead URL to a public LinkedIn profile URL.
    Sales Nav URLs look like: /sales/lead/ACwAAAXXXXX,name,...
    We strip to get the vanity URL or member ID if available.
    For simplicity, return the original URL — the scraper handles Sales Nav profiles too.
    """
    if sales_url.startswith("/"):
        return "https://www.linkedin.com" + sales_url
    return sales_url
