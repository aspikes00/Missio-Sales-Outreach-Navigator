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
    Handles both paginated lists and infinite-scroll lists.
    Returns basic profile info extracted directly from the list view —
    no individual profile visits needed.
    """
    logger.info("Syncing leads from Sales Navigator list...")
    page.goto(list_url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(random.uniform(3.0, 5.0))

    leads: list[ListLead] = []
    seen_urls: set[str] = set()
    stall_rounds = 0
    MAX_STALL_ROUNDS = 3

    while True:
        try:
            page.wait_for_selector(sel.SALES_NAV_LEAD_LIST_ITEM, timeout=15000)
        except PWTimeout:
            logger.warning("No lead items found — list may be empty or selector changed.")
            break

        # Try card containers first, fall back to name links
        cards = page.query_selector_all(sel.SALES_NAV_LEAD_CARD)
        if cards:
            for card in cards:
                lead = _parse_card(card)
                if lead and lead.linkedin_url not in seen_urls:
                    seen_urls.add(lead.linkedin_url)
                    leads.append(lead)
        else:
            items = page.query_selector_all(sel.SALES_NAV_LEAD_LIST_ITEM)
            for item in items:
                href = item.get_attribute("href") or ""
                url = _normalize_url(href)
                if not url or url in seen_urls:
                    continue
                name = item.inner_text().strip()
                parts = name.split(" ", 1)
                lead = ListLead(
                    linkedin_url=url,
                    full_name=name,
                    first_name=parts[0],
                    last_name=parts[1] if len(parts) > 1 else "",
                )
                seen_urls.add(url)
                leads.append(lead)

        logger.info("Total leads read so far: %d", len(leads))

        # Scroll down so pagination controls are visible
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(1.0, 1.5))

        # Log all buttons for debugging (first page only)
        if len(leads) <= 25:
            all_btns = page.query_selector_all("button")
            btn_labels = []
            for b in all_btns:
                label = b.get_attribute("aria-label") or b.inner_text().strip()
                if label:
                    btn_labels.append(label[:60])
            logger.info("Buttons on page: %s", btn_labels)

        # Try several possible Next button selectors
        next_btn = None
        for next_sel in sel.SALES_NAV_PAGINATION_NEXT_CANDIDATES:
            candidate = page.query_selector(next_sel)
            if candidate and not candidate.is_disabled():
                next_btn = candidate
                logger.info("Found Next button via selector: %s", next_sel)
                break

        if next_btn:
            next_btn.scroll_into_view_if_needed()
            time.sleep(random.uniform(0.8, 1.5))
            next_btn.click()
            logger.info("Clicked Next — loading next page...")
            time.sleep(random.uniform(3.0, 4.5))
            stall_rounds = 0
            continue

        # No pagination button found — try infinite scroll
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2.0, 3.0))

        new_cards = page.query_selector_all(sel.SALES_NAV_LEAD_CARD)
        new_count = 0
        for card in new_cards:
            lead = _parse_card(card)
            if lead and lead.linkedin_url not in seen_urls:
                seen_urls.add(lead.linkedin_url)
                leads.append(lead)
                new_count += 1

        if new_count == 0:
            stall_rounds += 1
            if stall_rounds >= MAX_STALL_ROUNDS:
                logger.info("No new leads after %d scroll attempts — list fully read.", MAX_STALL_ROUNDS)
                break
        else:
            stall_rounds = 0
            logger.info("Scroll loaded %d more leads (total: %d)", new_count, len(leads))

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
