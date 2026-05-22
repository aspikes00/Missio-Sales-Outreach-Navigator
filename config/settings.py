from __future__ import annotations
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # pip install tomli for <3.11


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
class BrandConfig:
    slug: str
    name: str
    description: str
    value_prop: str
    voice_notes: str     # brand-specific voice, forbidden phrases, pain language
    cta_type: str        # "discovery_call" | "free_trial"
    cta_url: str
    sales_nav_list_url: str
    sales_nav_list_name: str   # exact list name as it appears in Sales Navigator
    sales_nav_search_url: str  # search URL with ICP filters pre-applied (for populate-list)
    daily_connection_limit: int
    daily_message_limit: int
    templates_dir: Path

    def load_template(self, name: str) -> str:
        path = self.templates_dir / name
        if not path.exists():
            raise FileNotFoundError(
                f"Template not found: {path}\n"
                f"Create it inside brands/{self.slug}/templates/"
            )
        return path.read_text(encoding="utf-8").strip()

    @property
    def cta_label(self) -> str:
        return "discovery call" if self.cta_type == "discovery_call" else "free trial"


@dataclass
class Settings:
    linkedin_email: str
    linkedin_password: str
    anthropic_api_key: str

    business_hours_start: int
    business_hours_end: int
    timezone: str

    db_path: Path
    cookies_path: Path
    log_path: Path

    anthropic_model: str
    headless_browser: bool
    session_warmup_days: int
    max_consecutive_errors: int
    min_delay_seconds: int
    max_delay_seconds: int

    brands_dir: Path = field(init=False)

    def __post_init__(self):
        self.brands_dir = BASE_DIR / "brands"
        self.db_path = BASE_DIR / self.db_path
        self.cookies_path = BASE_DIR / self.cookies_path
        self.log_path = BASE_DIR / self.log_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def load_brand(self, slug: str) -> BrandConfig:
        brand_dir = self.brands_dir / slug
        toml_path = brand_dir / "brand.toml"
        if not toml_path.exists():
            available = [d.name for d in self.brands_dir.iterdir() if d.is_dir() and (d / "brand.toml").exists()]
            raise FileNotFoundError(
                f"Brand config not found: {toml_path}\n"
                f"Available brands: {available or ['(none — create a folder under brands/)']}"
            )
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)

        b = data["brand"]
        o = data["outreach"]
        return BrandConfig(
            slug=slug,
            name=b["name"],
            description=b.get("description", ""),
            value_prop=b.get("value_prop", ""),
            voice_notes=b.get("voice_notes", ""),
            cta_type=o["cta_type"],
            cta_url=o["cta_url"],
            sales_nav_list_url=o.get("sales_nav_list_url", ""),
            sales_nav_list_name=o.get("sales_nav_list_name", ""),
            sales_nav_search_url=o.get("sales_nav_search_url", ""),
            daily_connection_limit=o.get("daily_connection_limit", 5),
            daily_message_limit=o.get("daily_message_limit", 8),
            templates_dir=brand_dir / "templates",
        )

    def list_brands(self) -> list[str]:
        if not self.brands_dir.exists():
            return []
        return [
            d.name for d in sorted(self.brands_dir.iterdir())
            if d.is_dir() and (d / "brand.toml").exists()
        ]


def load_settings() -> Settings:
    return Settings(
        linkedin_email=_require("LINKEDIN_EMAIL"),
        linkedin_password=_require("LINKEDIN_PASSWORD"),
        anthropic_api_key=_require("ANTHROPIC_API_KEY"),
        business_hours_start=_int("BUSINESS_HOURS_START", 9),
        business_hours_end=_int("BUSINESS_HOURS_END", 17),
        timezone=os.getenv("TIMEZONE", "America/Chicago"),
        db_path=Path(os.getenv("DB_PATH", "data/leads.db")),
        cookies_path=Path(os.getenv("COOKIES_PATH", "data/cookies.json")),
        log_path=Path(os.getenv("LOG_PATH", "logs/outreach.log")),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        headless_browser=_bool("HEADLESS_BROWSER", False),
        session_warmup_days=_int("SESSION_WARMUP_DAYS", 7),
        max_consecutive_errors=_int("MAX_CONSECUTIVE_ERRORS", 3),
        min_delay_seconds=_int("MIN_DELAY_SECONDS", 120),
        max_delay_seconds=_int("MAX_DELAY_SECONDS", 600),
    )
