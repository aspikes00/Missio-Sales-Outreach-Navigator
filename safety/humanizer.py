from __future__ import annotations
import logging
import random
import time

from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class Humanizer:
    def __init__(self, min_delay: int = 120, max_delay: int = 600):
        self._min_delay = min_delay
        self._max_delay = max_delay

    def type_text(self, page: Page, selector, text: str, element=None):
        """Type text character-by-character with realistic human timing."""
        el = element if element is not None else page.wait_for_selector(selector, timeout=10000)
        el.click()
        time.sleep(random.uniform(0.3, 0.8))

        for i, char in enumerate(text):
            page.keyboard.type(char)

            # Base typing speed: ~55 WPM = ~4.6 chars/sec = ~217ms per char
            base_delay = random.gauss(0.09, 0.04)
            base_delay = max(0.03, min(0.35, base_delay))

            # Micro-pause at punctuation
            if char in ".,!?;:":
                base_delay += random.uniform(0.1, 0.35)

            # Occasional longer thinking pause
            if i > 0 and i % random.randint(15, 30) == 0:
                base_delay += random.uniform(0.4, 1.8)

            # Very occasional typo + backspace
            if random.random() < 0.025 and i < len(text) - 1:
                wrong = random.choice("abcdefghijklmnopqrstuvwxyz")
                page.keyboard.type(wrong)
                time.sleep(random.uniform(0.12, 0.35))
                page.keyboard.press("Backspace")

            time.sleep(base_delay)

    def between_action_delay(self):
        """Human-paced wait between sending each message or connection request."""
        mean = (self._min_delay + self._max_delay) / 2
        std = (self._max_delay - self._min_delay) / 4
        delay = random.gauss(mean, std)
        delay = max(self._min_delay, min(self._max_delay, delay))
        logger.info("Waiting %.0f seconds before next action...", delay)
        time.sleep(delay)

    def pre_action_pause(self):
        """Short pause before clicking — simulates cursor travel time."""
        time.sleep(random.uniform(0.8, 2.5))

    def page_scroll(self, page: Page, scrolls: int = 4):
        """Scroll the page slowly to simulate reading behavior."""
        for _ in range(scrolls):
            page.mouse.wheel(0, random.randint(250, 550))
            time.sleep(random.uniform(0.3, 0.9))
