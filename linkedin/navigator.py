from __future__ import annotations
import logging
import time
import random
from dataclasses import dataclass, field

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)


@dataclass
class ListLead:
    linkedin_url: str
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    company_name: str = ""
    location: str = ""


def sync_leads_from_list(page: Page, list_url: str) -> list[ListLead]:
    """
    Read every lead card from a Sales Navigator saved list.
    Returns basic profile info extracted directly from the list view —
    no individual profile visits needed.
    """
    logger.info("Syncing leads from Sales Navigator list...")
    page.goto(list_url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(random.uniform(3.0, 5.0))

    leads: list[ListLead] = []
    page_num = 1

    while True:
        logger.info("Reading list page %d...", page_num)

        try:
            page.wait_for_selector(sel.SALES_NAV_LEAD_LIST_ITEM, timeout=15000)
        except PWTimeout:
            logger.warning("No leads found on page %d — list may be empty or selector changed.", page_num)
            break

        cards = page.query_selector_all(sel.SALES_NAV_LEAD_CARD)

        # Fallback: if card container selector fails, grab name links directly
        if not cards:
            items = page.query_selector_all(sel.SALES_NAV_LEAD_LIST_ITEM)
            for item in items:
                href = item.get_attribute("href") or ""
                url = _normalize_url(href)
                if not url:
                    continue
                name = item.inner_text().strip()
                parts = name.split(" ", 1)
                lead = ListLead(
                    linkedin_url=url,
                    full_name=name,
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else "",
                )
                if url not in {l.linkedin_url for l in leads}:
                    leads.append(lead)
        else:
            for card in cards:
                lead = _parse_card(card)
                if lead and lead.linkedin_url not in {l.linkedin_url for l in leads}:
                    leads.append(lead)

        logger.info("Total leads read so far: %d", len(leads))

        # Scroll to bottom to ensure pagination button is visible
        page.mouse.wheel(0, 800)
        time.sleep(random.uniform(0.5, 1.0))

        next_btn = page.query_selector(sel.SALES_NAV_PAGINATION_NEXT)
        if not next_btn or next_btn.is_disabled():
            logger.info("Reached last page of list.")
            break

        next_btn.click()
        page_num += 1
        time.sleep(random.uniform(2.5, 4.5))

    logger.info("Sync complete — %d leads read from list.", len(leads))
    return leads


def _parse_card(card) -> ListLead | None:
    try:
        name_el = card.query_selector(sel.SALES_NAV_CARD_NAME)
        if not name_el:
            return None

        href = name_el.get_attribute("href") or ""
        url = _normalize_url(href)
        if not url:
            return None

        full_name = name_el.inner_text().strip()
        parts = full_name.split(" ", 1)

        title_el = card.query_selector(sel.SALES_NAV_CARD_TITLE)
        company_el = card.query_selector(sel.SALES_NAV_CARD_COMPANY)
        location_el = card.query_selector(sel.SALES_NAV_CARD_LOCATION)

        return ListLead(
            linkedin_url=url,
            full_name=full_name,
            first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else "",
            title=title_el.inner_text().strip() if title_el else "",
            company_name=company_el.inner_text().strip() if company_el else "",
            location=location_el.inner_text().strip() if location_el else "",
        )
    except Exception as e:
        logger.debug("Could not parse lead card: %s", e)
        return None


def get_lead_urls_from_list(page: Page, list_url: str, max_leads: int = 200) -> list[str]:
    """Return profile URLs from a Sales Navigator saved list (used by outreach run)."""
    leads = sync_leads_from_list(page, list_url)
    return [l.linkedin_url for l in leads[:max_leads]]


def navigate_to_profile(page: Page, profile_url: str) -> bool:
    try:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(1.5, 3.0))
        return True
    except PWTimeout:
        logger.warning("Timeout navigating to %s", profile_url)
        return False


def _normalize_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("/"):
        return "https://www.linkedin.com" + href
    if href.startswith("http"):
        return href
    return ""
