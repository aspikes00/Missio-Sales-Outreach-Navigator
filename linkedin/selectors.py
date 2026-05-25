from __future__ import annotations
# All LinkedIn CSS selectors isolated here.
# When LinkedIn updates their frontend, only this file needs updating.

# --- Login page ---
LOGIN_EMAIL_INPUT = 'input[id="username"]'
LOGIN_PASSWORD_INPUT = 'input[id="password"]'
LOGIN_SUBMIT_BUTTON = 'button[type="submit"]'
LOGIN_ERROR_BANNER = '.alert-content'
CAPTCHA_INDICATOR = '.challenge-dialog'

# --- Feed / nav (proves logged in) ---
FEED_NAV = 'nav[aria-label="Primary"]'

# --- Profile page ---
PROFILE_NAME = 'h1.text-heading-xlarge'
PROFILE_HEADLINE = '.text-body-medium.break-words'
PROFILE_TITLE = '.mr1.hoverable-link-text'
PROFILE_COMPANY = '.pv-text-details__right-panel-item-text'
PROFILE_LOCATION = '.text-body-small.inline.t-black--light'
PROFILE_ABOUT = '#about ~ .display-flex .inline-show-more-text'

# --- Profile action buttons ---
CONNECT_BUTTON = 'button[aria-label^="Connect"]'
MESSAGE_BUTTON = 'button[aria-label^="Message"]'
PENDING_BUTTON = 'button[aria-label^="Pending"]'
CONNECT_BUTTON_CANDIDATES = [
    'button[aria-label^="Connect"]',
    'button[aria-label*="to connect"]',   # "Invite [Name] to connect"
    'button[aria-label^="Invite"]',
]
# NOTE: only use these on regular /in/ profile pages — on Sales Nav, Message ≠ connected
ALREADY_CONNECTED_CANDIDATES = [
    'button[aria-label^="Message"]',
    'button:has-text("Message")',
]
ALREADY_PENDING_CANDIDATES = [
    'button[aria-label^="Pending"]',
    'button[aria-label*="Invitation sent"]',
    'button[aria-label*="pending"]',
    'button:has-text("Pending")',
    'button:has-text("Sent")',
]

# --- Sales Navigator: "..." overflow menu → Connect ---
SALES_NAV_MORE_BTN_CANDIDATES = [
    'button[aria-label="Open actions overflow menu"]',
    'button[aria-label="More actions"]',
    'button[aria-label="More options"]',
]
SALES_NAV_DROPDOWN_CONNECT_CANDIDATES = [
    'div[aria-label="Connect"]',
    '[role="option"]:has-text("Connect")',
    '.artdeco-dropdown__item:has-text("Connect")',
    # Playwright text engine — exact match, most reliable
    'text="Connect"',
    ':text-is("Connect")',
]

# --- Connect modal ---
CONNECT_ADD_NOTE_BUTTON_CANDIDATES = [
    'button[aria-label="Add a note"]',
    'button:has-text("Add a note")',
]
CONNECT_NOTE_TEXTAREA_CANDIDATES = [
    'textarea[name="message"]',
    'textarea[placeholder*="note" i]',
    'textarea',
]
CONNECT_SEND_BUTTON_CANDIDATES = [
    'button[aria-label="Send invitation"]',
    'button[aria-label="Send now"]',
    'button:has-text("Send now")',
    'button:has-text("Send invitation")',
    'button[type="submit"]:has-text("Send")',
]
CONNECT_SEND_WITHOUT_NOTE_CANDIDATES = [
    'button[aria-label="Send without a note"]',
    'button:has-text("Send without a note")',
]
# Keep single-value aliases for code that still uses the old names
CONNECT_ADD_NOTE_BUTTON = CONNECT_ADD_NOTE_BUTTON_CANDIDATES[0]
CONNECT_NOTE_TEXTAREA = CONNECT_NOTE_TEXTAREA_CANDIDATES[0]
CONNECT_SEND_BUTTON = CONNECT_SEND_BUTTON_CANDIDATES[0]
CONNECT_SEND_WITHOUT_NOTE = CONNECT_SEND_WITHOUT_NOTE_CANDIDATES[0]

# --- Message composer ---
MESSAGE_COMPOSE_TEXTAREA = '.msg-form__contenteditable'
MESSAGE_SEND_BUTTON = 'button.msg-form__send-button'

# --- Sales Navigator: saved list reading ---
SALES_NAV_LEAD_LIST_ITEM    = 'a[data-anonymize="person-name"]'
SALES_NAV_LEAD_CARD         = 'li[data-view-name="people-list-lead-item"]'
SALES_NAV_CARD_NAME         = '[data-anonymize="person-name"]'
SALES_NAV_CARD_TITLE        = '[data-anonymize="job-title"]'
SALES_NAV_CARD_COMPANY      = '[data-anonymize="company-name"]'
SALES_NAV_CARD_LOCATION     = '[data-anonymize="person-location"]'
SALES_NAV_PAGINATION_NEXT   = 'button[aria-label="Next"]'
SALES_NAV_PAGINATION_NEXT_CANDIDATES = [
    'button:has-text("Next")',
    'button[aria-label="Next"]',
    'button[aria-label="Next page"]',
    'li.artdeco-pagination__button--next button',
    'button.artdeco-pagination__button--next',
    '[data-view-name="list-pagination-next-button"]',
]
SALES_NAV_LEAD_COUNT        = '.artdeco-pill__text'

# --- Sales Navigator: search results + bulk list population ---
# These appear on the /sales/search/people results page.
# If LinkedIn updates their frontend, update these constants and re-run.
SALES_NAV_SEARCH_RESULT_ROW = 'li[data-view-name="search-results-lead"]'
SALES_NAV_SELECT_ALL_CHECKBOX = 'input[data-view-name="search-results-select-all-checkbox"]'
SALES_NAV_SELECT_ALL_LABEL = 'label[data-view-name="search-results-select-all-label"]'
SALES_NAV_SELECTED_COUNT = '[data-view-name="search-results-selected-count"]'
SALES_NAV_SAVE_TO_LIST_BTN = 'button[data-view-name="search-results-save-to-list"]'
# Fallback button text matches (LinkedIn sometimes uses text-based buttons)
SALES_NAV_SAVE_TO_LIST_BTN_ALT = 'button:has-text("Save to list")'
SALES_NAV_LIST_MODAL = '[data-view-name="save-to-list-modal"]'
SALES_NAV_LIST_SEARCH_INPUT = '[data-view-name="save-to-list-search-input"]'
SALES_NAV_LIST_OPTION = '[data-view-name="save-to-list-option"]'
SALES_NAV_LIST_SAVE_BTN = 'button[data-view-name="save-to-list-save-button"]'
SALES_NAV_LIST_SAVE_BTN_ALT = 'button:has-text("Save")'
SALES_NAV_SEARCH_TOTAL_COUNT = '[data-view-name="search-results-total-count"]'
SALES_NAV_NO_RESULTS = '[data-view-name="search-results-no-results"]'

# --- Activity / Posts ---
ACTIVITY_LINK = 'a[href*="/recent-activity/"]'
POST_TEXT = '.feed-shared-update-v2__description'

# --- Messaging inbox ---
INBOX_CONVERSATION_LIST = '.msg-conversations-container__conversations-list li'
INBOX_SENDER_NAME = '.msg-conversation-listitem__participant-names'
INBOX_UNREAD_INDICATOR = '.msg-conversation-listitem__unread-count'

# --- Rate limit / warning banners ---
RATE_LIMIT_BANNER = '[aria-label*="weekly invitation limit"]'
GENERIC_ERROR_BANNER = '.ip-fuse-limit-alert'

# --- Sales Navigator: InMail compose ---
# Selectors for sending InMail from a Sales Nav lead page (/sales/lead/...)
SALES_NAV_INMAIL_BTN_CANDIDATES = [
    'button[data-view-name="lead-actions-top-card-inmail-button"]',
    'button[aria-label*="InMail"]',
    'button[aria-label*="Message"]',
    'button:has-text("Message")',
    'button:has-text("InMail")',
]
SALES_NAV_INMAIL_SUBJECT = 'input[name="subject"], input[placeholder*="ubject"], input[aria-label*="ubject"]'
SALES_NAV_INMAIL_BODY_CANDIDATES = [
    'textarea[name="body"]',
    'textarea[aria-label*="ody"]',
    '.msg-form__contenteditable',
    'div[contenteditable="true"]',
]
SALES_NAV_INMAIL_SEND_BTN = 'button[aria-label*="end InMail"], button[type="submit"]:has-text("Send")'
