import logging
import time
import random

from playwright.sync_api import Page, TimeoutError as PWTimeout

from linkedin import selectors as sel

logger = logging.getLogger(__name__)

CONNECTION_NOTE_LIMIT = 300


class MessengerError(Exception):
    pass


def send_connection_request(page: Page, profile_url: str, note: str, humanizer) -> bool:
    if len(note) > CONNECTION_NOTE_LIMIT:
        raise ValueError(f"Connection note exceeds {CONNECTION_NOTE_LIMIT} chars: {len(note)}")

    logger.info("Sending connection request to %s", profile_url)

    if page.url != profile_url:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2.0, 4.0))

    humanizer.page_scroll(page)
    humanizer.pre_action_pause()

    connect_btn = page.query_selector(sel.CONNECT_BUTTON)
    if not connect_btn:
        more_btn = page.query_selector('button[aria-label="More actions"]')
        if more_btn:
            more_btn.click()
            time.sleep(random.uniform(0.8, 1.5))
            connect_btn = page.query_selector(sel.CONNECT_BUTTON)

    if not connect_btn:
        logger.warning("No Connect button found on %s (may already be connected or pending)", profile_url)
        return False

    connect_btn.click()
    time.sleep(random.uniform(1.0, 2.0))

    add_note_btn = page.query_selector(sel.CONNECT_ADD_NOTE_BUTTON)
    if add_note_btn:
        add_note_btn.click()
        time.sleep(random.uniform(0.8, 1.5))
        humanizer.type_text(page, sel.CONNECT_NOTE_TEXTAREA, note)
        time.sleep(random.uniform(0.5, 1.2))
    else:
        send_without = page.query_selector(sel.CONNECT_SEND_WITHOUT_NOTE)
        if send_without:
            send_without.click()
            logger.info("Sent connection request without note (modal variant).")
            return True

    send_btn = page.query_selector(sel.CONNECT_SEND_BUTTON)
    if not send_btn:
        raise MessengerError("Could not find Send button in connection modal.")

    humanizer.pre_action_pause()
    send_btn.click()
    time.sleep(random.uniform(1.5, 3.0))
    logger.info("Connection request sent.")
    return True


def send_direct_message(page: Page, profile_url: str, message: str, humanizer) -> bool:
    logger.info("Sending direct message to %s", profile_url)

    if page.url != profile_url:
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(2.0, 4.0))

    humanizer.page_scroll(page)
    humanizer.pre_action_pause()

    msg_btn = page.query_selector(sel.MESSAGE_BUTTON)
    if not msg_btn:
        logger.warning("No Message button found on %s — not a 1st-degree connection?", profile_url)
        return False

    msg_btn.click()
    time.sleep(random.uniform(1.5, 2.5))

    try:
        page.wait_for_selector(sel.MESSAGE_COMPOSE_TEXTAREA, timeout=10000)
    except PWTimeout:
        raise MessengerError("Message compose box did not open.")

    humanizer.type_text(page, sel.MESSAGE_COMPOSE_TEXTAREA, message)
    time.sleep(random.uniform(0.8, 1.5))

    humanizer.pre_action_pause()

    send_btn = page.wait_for_selector(sel.MESSAGE_SEND_BUTTON, timeout=8000)
    send_btn.click()
    time.sleep(random.uniform(1.5, 3.0))

    logger.info("Direct message sent.")
    return True


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
