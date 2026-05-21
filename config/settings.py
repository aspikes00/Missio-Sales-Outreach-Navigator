import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Required environment variable {key!r} is not set. See .env.example.")
    return val


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


def _bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


@dataclass
class Settings:
    linkedin_email: str
    linkedin_password: str
    anthropic_api_key: str
    calendly_link: str

    daily_connection_limit: int
    daily_message_limit: int
    min_delay_seconds: int
    max_delay_seconds: int

    business_hours_start: int
    business_hours_end: int
    timezone: str

    db_path: Path
    cookies_path: Path
    log_path: Path

    sales_nav_list_url: str
    anthropic_model: str

    headless_browser: bool
    session_warmup_days: int
    max_consecutive_errors: int

    templates_dir: Path = field(init=False)

    def __post_init__(self):
        self.templates_dir = BASE_DIR / "config" / "templates"
        self.db_path = BASE_DIR / self.db_path
        self.cookies_path = BASE_DIR / self.cookies_path
        self.log_path = BASE_DIR / self.log_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def load_template(self, name: str) -> str:
        path = self.templates_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path}")
        return path.read_text(encoding="utf-8").strip()


def load_settings() -> Settings:
    return Settings(
        linkedin_email=_require("LINKEDIN_EMAIL"),
        linkedin_password=_require("LINKEDIN_PASSWORD"),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        calendly_link=_require("CALENDLY_LINK"),
        daily_connection_limit=_int("DAILY_CONNECTION_LIMIT", 5),
        daily_message_limit=_int("DAILY_MESSAGE_LIMIT", 8),
        min_delay_seconds=_int("MIN_DELAY_SECONDS", 120),
        max_delay_seconds=_int("MAX_DELAY_SECONDS", 600),
        business_hours_start=_int("BUSINESS_HOURS_START", 9),
        business_hours_end=_int("BUSINESS_HOURS_END", 17),
        timezone=os.getenv("TIMEZONE", "America/Chicago"),
        db_path=Path(os.getenv("DB_PATH", "data/leads.db")),
        cookies_path=Path(os.getenv("COOKIES_PATH", "data/cookies.json")),
        log_path=Path(os.getenv("LOG_PATH", "logs/outreach.log")),
        sales_nav_list_url=os.getenv("SALES_NAV_LIST_URL", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        headless_browser=_bool("HEADLESS_BROWSER", False),
        session_warmup_days=_int("SESSION_WARMUP_DAYS", 7),
        max_consecutive_errors=_int("MAX_CONSECUTIVE_ERRORS", 3),
    )
