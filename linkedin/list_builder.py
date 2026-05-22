from __future__ import annotations
import logging
import random
import time

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)

# Sales Navigator allows max 25 results per page
LEADS_PER_PAGE = 25
# Safe daily ceiling for bulk list operations — well under LinkedIn's limits
DEFAULT_MAX_PER_SESSION = 200


class ListBuilderError(Exception):
    pass


class SelectorOutdatedError(ListBuilderError):
    """Raised when a Sales Navigator selector no longer matches the DOM."""
    pass


def populate_list_from_search(
    page: Page,
    search_url: str,
    list_name: str,
    humanizer,
    max_per_session: int = DEFAULT_MAX_PER_SESSION,
    start_page: int = 1,
) -> dict:
    """
    Page through a Sales Navigator search and bulk-add all results to a saved list.

    Returns a summary dict: {added, pages_processed, stopped_reason}
    """
    logger.info("Starting list population: list='%s', max=%d", list_name, max_per_session)

    total_added = 0
    pages_processed = 0
    stopped_reason = "completed"

    _navigate_to_search(page, search_url, start_page)

    while total_added < max_per_session:
        current_page = start_page + pages_processed
        logger.info("Processing search results page %d...", current_page)

        # Wait for results to render
        try:
            page.wait_for_selector(sel.SALES_NAV_SEARCH_RESULT_ROW, timeout=15000)
        except PWTimeout:
            if page.query_selector(sel.SALES_NAV_NO_RESULTS):
                logger.info("No more results — search exhausted.")
                stopped_reason = "no_more_results"
                break
            raise SelectorOutdatedError(
                "Could not find search result rows. "
                "The Sales Navigator DOM may have changed. "
                f"Update SALES_NAV_SEARCH_RESULT_ROW in linkedin/selectors.py.\n"
                f"Current value: {sel.SALES_NAV_SEARCH_RESULT_ROW}"
            )

        humanizer.page_scroll(page, scrolls=3)
        humanizer.pre_action_pause()

        # Select all leads on this page
        selected = _select_all_on_page(page)
        if not selected:
            logger.warning("Page %d: could not select leads — skipping page.", current_page)
            pages_processed += 1
            if not _go_to_next_page(page, humanizer):
                stopped_reason = "no_next_page"
                break
            continue

        logger.info("Page %d: selected leads.", current_page)

        # Add selected leads to the named list
        added_this_page = _add_selected_to_list(page, list_name, humanizer)
        if added_this_page is None:
            logger.error("Page %d: add-to-list operation failed. Stopping.", current_page)
            stopped_reason = "add_to_list_failed"
            break

        total_added += added_this_page
        pages_processed += 1
        logger.info(
            "Page %d complete: +%d leads added (total: %d / %d)",
            current_page, added_this_page, total_added, max_per_session,
        )

        if total_added >= max_per_session:
            stopped_reason = "session_limit_reached"
            logger.info("Session limit of %d reached. Run again tomorrow to continue.", max_per_session)
            break

        # Human delay between pages — shorter than outreach delays but still realistic
        delay = random.uniform(8, 20)
        logger.info("Waiting %.0fs before next page...", delay)
        time.sleep(delay)

        if not _go_to_next_page(page, humanizer):
            stopped_reason = "no_next_page"
            break

    result = {
        "added": total_added,
        "pages_processed": pages_processed,
        "stopped_reason": stopped_reason,
        "resume_from_page": start_page + pages_processed,
    }
    logger.info("List population complete: %s", result)
    return result


def _navigate_to_search(page: Page, search_url: str, start_page: int):
    url = search_url
    if start_page > 1:
        # Sales Navigator uses &page=N in the query string
        if "page=" in url:
            import re
            url = re.sub(r"page=\d+", f"page={start_page}", url)
        else:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}page={start_page}"

    logger.info("Navigating to search URL (page %d)...", start_page)
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(random.uniform(3.0, 5.0))


def _select_all_on_page(page: Page) -> bool:
    """Click the 'select all on page' checkbox. Returns True if successful."""
    # Try the primary selector first
    for selector in [sel.SALES_NAV_SELECT_ALL_LABEL, sel.SALES_NAV_SELECT_ALL_CHECKBOX]:
        el = page.query_selector(selector)
        if el:
            try:
                el.click()
                time.sleep(random.uniform(0.8, 1.5))
                # Verify something got selected
                count_el = page.query_selector(sel.SALES_NAV_SELECTED_COUNT)
                if count_el:
                    logger.debug("Selected count indicator: %s", count_el.inner_text().strip())
                return True
            except Exception as e:
                logger.debug("Selector %s failed: %s", selector, e)
                continue

    logger.warning(
        "Could not find 'Select all' checkbox. "
        "LinkedIn may have updated their UI. "
        f"Check SALES_NAV_SELECT_ALL_LABEL / SALES_NAV_SELECT_ALL_CHECKBOX in selectors.py."
    )
    return False


def _add_selected_to_list(page: Page, list_name: str, humanizer) -> int | None:
    """
    Click 'Save to list', pick the named list, confirm.
    Returns number of leads added, or None on failure.
    """
    # Find and click the Save to list button
    save_btn = None
    for selector in [sel.SALES_NAV_SAVE_TO_LIST_BTN, sel.SALES_NAV_SAVE_TO_LIST_BTN_ALT]:
        save_btn = page.query_selector(selector)
        if save_btn:
            break

    if not save_btn:
        logger.error(
            "Could not find 'Save to list' button after selecting leads. "
            "Selectors to check: SALES_NAV_SAVE_TO_LIST_BTN in selectors.py."
        )
        return None

    humanizer.pre_action_pause()
    save_btn.click()
    time.sleep(random.uniform(1.5, 2.5))

    # Wait for the list selection modal
    try:
        page.wait_for_selector(sel.SALES_NAV_LIST_MODAL, timeout=10000)
    except PWTimeout:
        # Try text-based fallback — modal may load differently
        logger.debug("List modal selector timed out, trying search input directly...")

    # Search for the list by name in the modal input
    search_input = page.query_selector(sel.SALES_NAV_LIST_SEARCH_INPUT)
    if search_input:
        humanizer.type_text(page, sel.SALES_NAV_LIST_SEARCH_INPUT, list_name)
        time.sleep(random.uniform(0.8, 1.5))

    # Find and click the matching list option
    list_option = _find_list_option(page, list_name)
    if not list_option:
        logger.error(
            "Could not find list named '%s' in the Save to list modal. "
            "Make sure the list name in brand.toml matches exactly (case-sensitive).",
            list_name,
        )
        # Close modal by pressing Escape
        page.keyboard.press("Escape")
        return None

    list_option.click()
    time.sleep(random.uniform(0.6, 1.2))

    # Click the final Save/Confirm button
    confirm_btn = None
    for selector in [sel.SALES_NAV_LIST_SAVE_BTN, sel.SALES_NAV_LIST_SAVE_BTN_ALT]:
        confirm_btn = page.query_selector(selector)
        if confirm_btn and confirm_btn.is_enabled():
            break

    if not confirm_btn:
        logger.error("Could not find the Save confirmation button in the modal.")
        page.keyboard.press("Escape")
        return None

    humanizer.pre_action_pause()
    confirm_btn.click()
    time.sleep(random.uniform(2.0, 3.5))

    # LinkedIn doesn't always show an explicit count of what was added,
    # so we return LEADS_PER_PAGE as the expected adds (25 per page)
    return LEADS_PER_PAGE


def _find_list_option(page: Page, list_name: str):
    """Find the list option element matching list_name (case-insensitive partial match)."""
    options = page.query_selector_all(sel.SALES_NAV_LIST_OPTION)
    list_name_lower = list_name.lower().strip()
    for option in options:
        text = option.inner_text().strip().lower()
        if list_name_lower in text:
            return option
    # If no match on text, try aria-label
    for option in options:
        label = (option.get_attribute("aria-label") or "").lower()
        if list_name_lower in label:
            return option
    return None


def _go_to_next_page(page: Page, humanizer) -> bool:
    """Click the Next page button. Returns True if successful."""
    next_btn = page.query_selector(sel.SALES_NAV_PAGINATION_NEXT)
    if not next_btn or next_btn.is_disabled():
        logger.info("No next page button found — reached end of results.")
        return False

    humanizer.pre_action_pause()
    next_btn.click()
    time.sleep(random.uniform(3.0, 5.0))
    return True
