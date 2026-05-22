from __future__ import annotations
import json
import logging
import random
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from config.settings import Settings

logger = logging.getLogger(__name__)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class BrowserManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def __enter__(self) -> "BrowserManager":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self._settings.headless_browser,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        self._context = self._browser.new_context(
            user_agent=CHROME_UA,
            viewport={"width": 1440, "height": 900},
            timezone_id=self._settings.timezone,
            locale="en-US",
        )
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self._load_cookies()
        self.page = self._context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._save_cookies()
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _load_cookies(self):
        path = self._settings.cookies_path
        if path.exists():
            try:
                cookies = json.loads(path.read_text(encoding="utf-8"))
                self._context.add_cookies(cookies)
                logger.debug("Loaded %d cookies from %s", len(cookies), path)
            except Exception as e:
                logger.warning("Could not load cookies: %s", e)

    def _save_cookies(self):
        if not self._context:
            return
        try:
            cookies = self._context.cookies()
            self._settings.cookies_path.write_text(
                json.dumps(cookies, indent=2), encoding="utf-8"
            )
            logger.debug("Saved %d cookies", len(cookies))
        except Exception as e:
            logger.warning("Could not save cookies: %s", e)

    def human_delay(self, min_s: float = 2.0, max_s: float = 8.0):
        duration = random.uniform(min_s, max_s)
        time.sleep(duration)
