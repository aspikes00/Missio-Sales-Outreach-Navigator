from __future__ import annotations
import logging
import time
import random
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)


@dataclass
class ScrapedProfile:
    linkedin_url: str
    first_name: str = ""
    last_name: str = ""
    full_name: str = ""
    title: str = ""
    company_name: str = ""
    industry: str = ""
    location: str = ""
    headline: str = ""
    about_snippet: str = ""
    recent_posts: list[str] = field(default_factory=list)
    connection_degree: str = ""


def _resolve_linkedin_url(page: Page, url: str) -> str:
    """If url is a Sales Navigator lead URL, find and return the regular linkedin.com/in/ URL."""
    if "/sales/lead/" not in url:
        return url

    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(random.uniform(2.0, 3.5))

    # Sales Nav lead pages have a link to the regular profile
    for selector in [
        'a[data-anonymize="person-name"][href*="/in/"]',
        'a[href*="linkedin.com/in/"]',
        'a[href^="/in/"]',
    ]:
        el = page.query_selector(selector)
        if el:
            href = el.get_attribute("href") or ""
            if href.startswith("/"):
                href = "https://www.linkedin.com" + href
            if "/in/" in href:
                logger.info("Resolved Sales Nav URL → %s", href)
                return href

    logger.warning("Could not resolve Sales Nav URL to a regular profile: %s", url)
    return url


def scrape_profile(page: Page, profile_url: str) -> Optional[ScrapedProfile]:
    logger.info("Scraping profile: %s", profile_url)

    resolved_url = _resolve_linkedin_url(page, profile_url)

    if page.url != resolved_url:
        page.goto(resolved_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2.0, 4.0))

    profile = ScrapedProfile(linkedin_url=profile_url)

    profile.full_name = _safe_text(page, sel.PROFILE_NAME)
    if profile.full_name:
        parts = profile.full_name.strip().split(" ", 1)
        profile.first_name = parts[0]
        profile.last_name = parts[1] if len(parts) > 1 else ""

    profile.headline = _safe_text(page, sel.PROFILE_HEADLINE)
    profile.location = _safe_text(page, sel.PROFILE_LOCATION)

    title_el = page.query_selector(sel.PROFILE_TITLE)
    if title_el:
        profile.title = title_el.inner_text().strip()

    company_el = page.query_selector(sel.PROFILE_COMPANY)
    if company_el:
        profile.company_name = company_el.inner_text().strip()

    about_el = page.query_selector(sel.PROFILE_ABOUT)
    if about_el:
        profile.about_snippet = about_el.inner_text().strip()[:500]

    profile.connection_degree = _detect_connection_degree(page)

    _scroll_slowly(page)

    profile.recent_posts = _scrape_recent_posts(page, profile_url)

    logger.info(
        "Scraped: %s @ %s | Posts: %d",
        profile.full_name, profile.company_name, len(profile.recent_posts),
    )
    return profile


def _scrape_recent_posts(page: Page, profile_url: str) -> list[str]:
    posts = []
    navigated = False
    try:
        activity_link = page.query_selector(sel.ACTIVITY_LINK)
        if not activity_link:
            return posts

        activity_url = activity_link.get_attribute("href")
        if not activity_url:
            return posts

        if activity_url.startswith("/"):
            activity_url = "https://www.linkedin.com" + activity_url

        page.goto(activity_url, wait_until="domcontentloaded", timeout=15000)
        navigated = True
        time.sleep(random.uniform(2.0, 3.5))

        post_elements = page.query_selector_all(sel.POST_TEXT)
        for el in post_elements[:3]:
            text = el.inner_text().strip()
            if text and len(text) > 20:
                posts.append(text[:300])

    except Exception as e:
        logger.debug("Could not scrape recent posts: %s", e)
    finally:
        if navigated:
            page.go_back()
            time.sleep(random.uniform(1.0, 2.0))

    return posts


def _detect_connection_degree(page: Page) -> str:
    try:
        content = page.content()
        if "1st" in content and "degree connection" in content:
            return "1st"
        if "2nd" in content and "degree connection" in content:
            return "2nd"
        if "3rd" in content:
            return "3rd"
    except Exception:
        pass
    return ""


def check_connection_accepted(page: Page, profile_url: str) -> bool:
    if page.url != profile_url:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(1.5, 3.0))

    msg_btn = page.query_selector(sel.MESSAGE_BUTTON)
    if msg_btn:
        return True

    pending_btn = page.query_selector(sel.PENDING_BUTTON)
    if pending_btn:
        return False

    return False


def _safe_text(page: Page, selector: str) -> str:
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else ""
    except Exception:
        return ""


def _scroll_slowly(page: Page):
    for _ in range(4):
        page.mouse.wheel(0, random.randint(300, 600))
        time.sleep(random.uniform(0.4, 1.0))
