from __future__ import annotations
import logging
import time
import random

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)

CONNECTION_NOTE_LIMIT = 300


class MessengerError(Exception):
    pass


def _js_click(element) -> None:
    """Click via JavaScript — bypasses Playwright's visibility/stability wait."""
    element.evaluate("el => el.click()")


def send_connection_request(page: Page, profile_url: str, note: str, humanizer) -> bool:
    if len(note) > CONNECTION_NOTE_LIMIT:
        raise ValueError(f"Connection note exceeds {CONNECTION_NOTE_LIMIT} chars: {len(note)}")

    logger.info("Sending connection request to %s", profile_url)

    if page.url != profile_url:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2.0, 4.0))

    humanizer.page_scroll(page)
    humanizer.pre_action_pause()

    connect_btn = None
    for _csel in sel.CONNECT_BUTTON_CANDIDATES:
        connect_btn = page.query_selector(_csel)
        if connect_btn:
            logger.info("Found Connect button via: %s", _csel)
            break
    if not connect_btn:
        # Try overflow/More menus — collect all candidates to try.
        # Named selectors (Sales Nav, labeled buttons) come first; then fall back
        # to every unlabeled "More" button for creator-mode regular profiles.
        more_btns_to_try = []
        seen_els = set()
        for more_sel in sel.SALES_NAV_MORE_BTN_CANDIDATES:
            btn = page.query_selector(more_sel)
            if btn:
                eid = btn.evaluate("el => el.outerHTML.substring(0, 80)")
                if eid not in seen_els:
                    seen_els.add(eid)
                    more_btns_to_try.append(btn)
        for btn in page.query_selector_all("button"):
            if btn.inner_text().strip() == "More" and not btn.get_attribute("aria-label"):
                eid = btn.evaluate("el => el.outerHTML.substring(0, 80)")
                if eid not in seen_els:
                    seen_els.add(eid)
                    more_btns_to_try.append(btn)

        for more_btn in more_btns_to_try:
            try:
                more_btn.click(timeout=5000)
            except Exception:
                _js_click(more_btn)
            time.sleep(random.uniform(1.2, 2.0))

            connect_btn = page.query_selector(sel.CONNECT_BUTTON)
            if not connect_btn:
                for dropdown_sel in sel.SALES_NAV_DROPDOWN_CONNECT_CANDIDATES:
                    candidate = page.query_selector(dropdown_sel)
                    if candidate:
                        connect_btn = candidate
                        logger.info("Found Connect in dropdown via: %s", dropdown_sel)
                        break
            if connect_btn:
                break
            # Not this More button — close dropdown and try the next one
            page.keyboard.press("Escape")
            time.sleep(0.5)

    if not connect_btn:
        _all_btns = page.query_selector_all("button")
        _btn_labels = [
            b.get_attribute("aria-label") or b.inner_text().strip()[:50]
            for b in _all_btns
            if (b.get_attribute("aria-label") or b.inner_text().strip())
        ]
        logger.warning(
            "No Connect button found on %s. Visible buttons: %s", profile_url, _btn_labels[:20]
        )
        return False

    # Dismiss any spotlight/onboarding popup that has role="dialog" — it would
    # intercept our modal search since it appears before the connection modal.
    spotlight = page.query_selector('button[aria-label="Dismiss spotlight popup"]')
    if spotlight:
        _js_click(spotlight)
        time.sleep(0.4)

    _js_click(connect_btn)
    time.sleep(random.uniform(1.5, 2.5))

    # Find the connection modal specifically — iterate all dialogs and pick the
    # one that contains connection-modal content (note textarea or send buttons).
    modal = None
    for dlg in page.query_selector_all('[role="dialog"]'):
        if (dlg.query_selector('button[aria-label="Add a note"]') or
                dlg.query_selector('button:has-text("Add a note")') or
                dlg.query_selector('textarea') or
                dlg.query_selector('button[aria-label*="Send invitation"]') or
                dlg.query_selector('button[aria-label="Send without a note"]') or
                dlg.query_selector('button:has-text("Send without a note")')):
            modal = dlg
            break
    if not modal:
        modal = page.query_selector('[role="dialog"]')
    ctx = modal if modal else page

    add_note_btn = None
    for sel_ in sel.CONNECT_ADD_NOTE_BUTTON_CANDIDATES:
        add_note_btn = ctx.query_selector(sel_)
        if add_note_btn:
            break

    if add_note_btn:
        _js_click(add_note_btn)
        time.sleep(random.uniform(0.8, 1.5))
        textarea = None
        for sel_ in sel.CONNECT_NOTE_TEXTAREA_CANDIDATES:
            textarea = ctx.query_selector(sel_)
            if textarea:
                break
        if textarea:
            humanizer.type_text(page, None, note, element=textarea)
        time.sleep(random.uniform(0.5, 1.2))
    else:
        send_without = None
        for sel_ in sel.CONNECT_SEND_WITHOUT_NOTE_CANDIDATES:
            send_without = ctx.query_selector(sel_)
            if send_without:
                break
        if send_without:
            _js_click(send_without)
            logger.info("Sent connection request without note (modal variant).")
            return True

    send_btn = None
    for sel_ in sel.CONNECT_SEND_BUTTON_CANDIDATES:
        send_btn = ctx.query_selector(sel_)
        if send_btn:
            break
    if not send_btn:
        all_btns = page.query_selector_all("button")
        btn_labels = [
            b.get_attribute("aria-label") or b.inner_text().strip()[:50]
            for b in all_btns
            if (b.get_attribute("aria-label") or b.inner_text().strip())
        ]
        logger.warning("Modal buttons visible: %s", btn_labels)
        raise MessengerError("Could not find Send button in connection modal.")

    humanizer.pre_action_pause()
    _js_click(send_btn)
    time.sleep(random.uniform(1.5, 3.0))
    logger.info("Connection request sent.")
    return True


def send_direct_message(page: Page, profile_url: str, message: str, humanizer) -> bool:
    logger.info("Sending direct message to %s", profile_url)

    # Always navigate fresh — after scraping scrolls/navigates to activity page and back,
    # the page is in a stale JS state where action buttons may not be rendered even if
    # page.url already matches. A fresh goto guarantees a clean hydrated page.
    page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
    time.sleep(random.uniform(2.0, 4.0))

    humanizer.page_scroll(page)
    humanizer.pre_action_pause()

    # Wait for Message button to appear — LinkedIn hydrates profile action buttons
    # asynchronously after domcontentloaded.
    msg_btn = None
    try:
        msg_btn = page.wait_for_selector(sel.MESSAGE_BUTTON, timeout=8000)
    except PWTimeout:
        pass
    if not msg_btn:
        logger.warning("No Message button found on %s — not a 1st-degree connection?", profile_url)
        return False

    msg_btn.click()
    time.sleep(random.uniform(1.5, 2.5))

    # Try multiple compose selectors — Sales Nav may navigate to /messaging/ or open a
    # different compose UI that uses div[contenteditable] instead of the classic class.
    compose_el = None
    for csel, timeout_ms in [
        (sel.MESSAGE_COMPOSE_TEXTAREA, 10000),              # classic LinkedIn floating chat
        ('div[contenteditable="true"][data-placeholder]', 8000),  # Sales Nav / new UI
        ('div[contenteditable="true"]', 6000),              # broad fallback
    ]:
        try:
            el = page.wait_for_selector(csel, timeout=timeout_ms)
            if el:
                compose_el = el
                logger.debug("Compose box found via selector: %s", csel)
                break
        except PWTimeout:
            continue

    if not compose_el:
        raise MessengerError("Message compose box did not open.")

    humanizer.type_text(page, None, message, element=compose_el)
    time.sleep(random.uniform(0.8, 1.5))

    humanizer.pre_action_pause()

    send_btn = None
    for ssel, timeout_ms in [
        (sel.MESSAGE_SEND_BUTTON, 8000),
        ('button[aria-label*="Send"]', 5000),
        ('button[type="submit"]:not([disabled])', 4000),
    ]:
        try:
            btn = page.wait_for_selector(ssel, timeout=timeout_ms)
            if btn:
                send_btn = btn
                break
        except PWTimeout:
            continue

    if not send_btn:
        raise MessengerError("Could not find message send button.")

    send_btn.click()
    time.sleep(random.uniform(1.5, 3.0))

    logger.info("Direct message sent.")
    return True


def send_inmail(page: Page, sales_nav_url: str, subject: str, body: str, humanizer) -> bool:
    """Send a Sales Navigator InMail. Navigates to the Sales Nav lead page to use the InMail button."""
    if "/sales/lead/" not in sales_nav_url:
        logger.warning("send_inmail called with non-Sales-Nav URL: %s", sales_nav_url)
        return False

    logger.info("Sending InMail to %s", sales_nav_url)

    if page.url != sales_nav_url:
        page.goto(sales_nav_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2.0, 3.5))

    humanizer.page_scroll(page)
    humanizer.pre_action_pause()

    # Find the InMail / Message button on the lead page
    inmail_btn = None
    for btn_sel in sel.SALES_NAV_INMAIL_BTN_CANDIDATES:
        candidate = page.query_selector(btn_sel)
        if candidate and not candidate.is_disabled():
            inmail_btn = candidate
            break

    if not inmail_btn:
        logger.warning("No InMail button found on Sales Nav lead page: %s", sales_nav_url)
        return False

    inmail_btn.click()
    time.sleep(random.uniform(1.5, 2.5))

    # Fill subject line
    try:
        subject_el = page.wait_for_selector(sel.SALES_NAV_INMAIL_SUBJECT, timeout=8000)
        subject_el.click()
        subject_el.fill(subject)
        time.sleep(random.uniform(0.5, 1.0))
    except PWTimeout:
        logger.warning("InMail subject field not found — modal may not have opened.")
        return False

    # Fill body
    body_el = None
    for body_sel in sel.SALES_NAV_INMAIL_BODY_CANDIDATES:
        candidate = page.query_selector(body_sel)
        if candidate:
            body_el = candidate
            break

    if not body_el:
        logger.warning("InMail body field not found.")
        return False

    body_el.click()
    time.sleep(random.uniform(0.3, 0.6))
    humanizer.type_text(page, None, body, element=body_el)
    time.sleep(random.uniform(0.8, 1.5))

    # Send
    humanizer.pre_action_pause()
    try:
        send_btn = page.wait_for_selector(sel.SALES_NAV_INMAIL_SEND_BTN, timeout=8000)
        send_btn.click()
        time.sleep(random.uniform(1.5, 3.0))
        logger.info("InMail sent.")
        return True
    except PWTimeout:
        # Fallback: look for any prominent Send button in the modal
        for send_sel in ['button[type="submit"]', 'button:has-text("Send")']:
            btn = page.query_selector(send_sel)
            if btn and not btn.is_disabled():
                btn.click()
                time.sleep(random.uniform(1.5, 3.0))
                logger.info("InMail sent (fallback send button).")
                return True
        logger.warning("Could not find InMail send button.")
        return False


def scan_inbox_for_replies(page: Page, active_lead_urls: list[str]) -> list[str]:
    """Return LinkedIn URLs of leads who have replied since last check."""
    replied = []
    try:
        page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=15000)
        time.sleep(random.uniform(2.0, 3.5))

        conversations = page.query_selector_all(sel.INBOX_CONVERSATION_LIST)
        for conv in conversations[:30]:
            unread = conv.query_selector(sel.INBOX_UNREAD_INDICATOR)
            if not unread:
                continue
            name_el = conv.query_selector(sel.INBOX_SENDER_NAME)
            if not name_el:
                continue
            sender_name = name_el.inner_text().strip().lower()
            for url in active_lead_urls:
                slug = url.rstrip("/").split("/")[-1].lower().replace("-", " ")
                if slug in sender_name or sender_name in slug:
                    replied.append(url)
                    break
    except Exception as e:
        logger.warning("Inbox scan failed: %s", e)
    return replied
