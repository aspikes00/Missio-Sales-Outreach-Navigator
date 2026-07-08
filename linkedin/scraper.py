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


def _resolve_linkedin_url(page: Page, url: str, full_name: str = "") -> str:
    """If url is a Sales Navigator lead URL, find and return the regular linkedin.com/in/ URL."""
    if "/sales/lead/" not in url:
        return url

    # Strip session-context suffix (e.g. ,NAME_SEARCH,xxxx) — these expire and cause redirects
    import re as _re
    clean_url = _re.sub(r'(/sales/lead/[^,/?]+),.*', r'\1', url)
    if clean_url != url:
        logger.debug("Stripped session context from URL: %s", url)

    page.goto(clean_url, wait_until="domcontentloaded", timeout=20000)

    # Wait for the lead page to hydrate — person-name signals content rendered
    try:
        page.wait_for_selector('[data-anonymize="person-name"]', timeout=8000)
    except PWTimeout:
        logger.debug("person-name element not found on Sales Nav page — page may not have loaded correctly")
    time.sleep(random.uniform(1.5, 2.5))

    # Strategy 1: JavaScript link extraction — returns absolute URLs regardless of href format
    try:
        in_links = page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(h => h && h.includes('/in/') && !h.includes('/sales/') && !h.includes('/mynetwork/'))
        """)
        for href in in_links:
            href = href.split("?")[0].rstrip("/")
            if "/in/" in href and "/sales/" not in href:
                logger.info("Resolved Sales Nav URL → %s", href)
                return href
    except Exception as e:
        logger.debug("JS link extraction failed: %s", e)

    # Strategy 2: CSS selector fallbacks (original approach)
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
            if "/in/" in href and "/sales/" not in href:
                href = href.split("?")[0]
                logger.info("Resolved Sales Nav URL via CSS → %s", href)
                return href

    # Strategy 3: Regex scan of full page HTML — catches URLs embedded in JSON or data attributes
    try:
        import re
        html = page.content()
        matches = re.findall(r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-]+)(?:[/?"\']|$)', html)
        if matches:
            resolved = f"https://www.linkedin.com/in/{matches[0]}"
            logger.info("Resolved Sales Nav URL via HTML scan → %s", resolved)
            return resolved
    except Exception as e:
        logger.debug("HTML scan failed: %s", e)

    # Strategy 4: LinkedIn people search by name — Sales Nav lead pages don't expose /in/ links
    # in their DOM, so we search regular LinkedIn using the stored full_name as a fallback.
    # We extract name+url pairs and verify the name loosely matches before accepting the URL,
    # to avoid sending messages addressed to "Belinda" to a completely different person.
    if full_name and full_name.strip():
        try:
            import urllib.parse
            search_url = (
                "https://www.linkedin.com/search/results/people/"
                f"?keywords={urllib.parse.quote(full_name.strip())}"
            )
            page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(random.uniform(1.5, 2.5))

            results = page.evaluate("""
                () => Array.from(document.querySelectorAll('a[href*="/in/"]'))
                    .map(a => ({href: a.href, name: (a.textContent || '').trim()}))
                    .filter(r => r.href
                        && !r.href.includes('/sales/')
                        && !r.href.includes('/mynetwork/')
                        && !r.href.includes('/search/'))
            """)
            # Use the first result whose visible name shares at least one word with the
            # searched name (case-insensitive). This blocks gross mismatches like
            # "Belinda" resolving to Tyler D. Carrigan.
            name_words = {w.lower() for w in full_name.split() if len(w) > 2}
            for r in results:
                href = (r.get("href") or "").split("?")[0].rstrip("/")
                if "/in/" not in href or "/sales/" in href:
                    continue
                result_name = r.get("name") or ""
                result_words = {w.lower() for w in result_name.split() if len(w) > 2}
                if name_words & result_words:  # at least one word overlaps
                    logger.info(
                        "Resolved Sales Nav URL via name search ('%s') → %s (result name: '%s')",
                        full_name, href, result_name,
                    )
                    return href
            logger.debug("Name search for '%s' found no name-matching result", full_name)
        except Exception as e:
            logger.debug("Name search fallback failed: %s", e)

    logger.warning("Could not resolve Sales Nav URL to a regular /in/ profile: %s", clean_url)
    # Return cleaned URL (session context stripped) — better than the expired original
    return clean_url


def scrape_profile(page: Page, profile_url: str, full_name: str = "") -> Optional[ScrapedProfile]:
    logger.info("Scraping profile: %s", profile_url)

    resolved_url = _resolve_linkedin_url(page, profile_url, full_name)

    if page.url != resolved_url:
        page.goto(resolved_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2.0, 4.0))

    profile = ScrapedProfile(linkedin_url=profile_url)

    # Wait for the name heading to render before extracting — LinkedIn lazy-loads profile cards.
    _NAME_CANDIDATES = [
        'h1.text-heading-xlarge',
        'h1[class*="text-heading"]',
        'h1',
    ]
    for _ns in _NAME_CANDIDATES:
        try:
            page.wait_for_selector(_ns, timeout=5000)
            break
        except PWTimeout:
            continue

    for _ns in _NAME_CANDIDATES:
        profile.full_name = _safe_text(page, _ns)
        if profile.full_name:
            break

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

    # Direct Message button = connected (regular profiles)
    if page.query_selector(sel.MESSAGE_BUTTON):
        return True

    # Pending button = request still pending
    if page.query_selector(sel.PENDING_BUTTON):
        return False

    # Direct Connect button = not connected
    for csel in sel.CONNECT_BUTTON_CANDIDATES:
        if page.query_selector(csel):
            return False

    # No direct button found — likely a creator-mode profile (Follow + More).
    # Open the More dropdown: if Connect is inside → not connected; if absent → connected.
    for more_sel in sel.SALES_NAV_MORE_BTN_CANDIDATES:
        more_btn = page.query_selector(more_sel)
        if more_btn:
            try:
                more_btn.click(timeout=3000)
            except Exception:
                more_btn.evaluate("el => el.click()")
            time.sleep(random.uniform(0.7, 1.2))

            connect_in_dropdown = any(
                page.query_selector(ds) for ds in sel.SALES_NAV_DROPDOWN_CONNECT_CANDIDATES
            )
            page.keyboard.press("Escape")
            time.sleep(0.3)
            return not connect_in_dropdown

    # Also try unlabeled "More" buttons (creator-mode regular profiles)
    for btn in page.query_selector_all("button"):
        if btn.inner_text().strip() == "More" and not btn.get_attribute("aria-label"):
            try:
                btn.click(timeout=3000)
            except Exception:
                btn.evaluate("el => el.click()")
            time.sleep(random.uniform(0.7, 1.2))

            connect_in_dropdown = any(
                page.query_selector(ds) for ds in sel.SALES_NAV_DROPDOWN_CONNECT_CANDIDATES
            )
            page.keyboard.press("Escape")
            time.sleep(0.3)
            return not connect_in_dropdown

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
