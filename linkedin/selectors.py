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

# --- Connect modal ---
CONNECT_ADD_NOTE_BUTTON = 'button[aria-label="Add a note"]'
CONNECT_NOTE_TEXTAREA = 'textarea[name="message"]'
CONNECT_SEND_BUTTON = 'button[aria-label="Send invitation"]'
CONNECT_SEND_WITHOUT_NOTE = 'button[aria-label="Send without a note"]'

# --- Message composer ---
MESSAGE_COMPOSE_TEXTAREA = '.msg-form__contenteditable'
MESSAGE_SEND_BUTTON = 'button.msg-form__send-button'

# --- Sales Navigator ---
SALES_NAV_LEAD_LIST_ITEM = 'a[data-anonymize="person-name"]'
SALES_NAV_PAGINATION_NEXT = 'button[aria-label="Next"]'
SALES_NAV_LEAD_COUNT = '.artdeco-pill__text'

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
