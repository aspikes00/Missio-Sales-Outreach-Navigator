from __future__ import annotations
import logging
from typing import Optional

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ai.prompts import CHAR_LIMITS, SYSTEM_PROMPT, VOICE_MEMO_CHAR_LIMIT, build_prompt, build_voice_memo_prompt
from config.settings import BrandConfig
from database.models import Lead

logger = logging.getLogger(__name__)


def _strip_em_dashes(text: str) -> str:
    """Replace em dashes (—) and double hyphens (--) with a regular dash or comma."""
    return text.replace("—", " - ").replace("--", " - ")


class MessageGenerator:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate(
        self,
        lead: Lead,
        stage: str,
        template: str,
        brand: BrandConfig,
        prior_messages: Optional[list[str]] = None,
    ) -> str:
        prompt = build_prompt(
            stage=stage,
            lead=lead,
            template=template,
            cta_url=brand.cta_url,
            cta_type=brand.cta_type,
            brand_name=brand.name,
            brand_description=brand.description,
            brand_value_prop=brand.value_prop,
            brand_voice_notes=brand.voice_notes,
            prior_messages=prior_messages,
            calendly_url=brand.calendly_url,
        )

        message = self._call_api(prompt)
        char_limit = CHAR_LIMITS.get(stage)

        if char_limit and len(message) > char_limit:
            logger.warning(
                "Generated message (%d chars) exceeds limit (%d). Retrying with explicit constraint.",
                len(message), char_limit,
            )
            message = self._call_api(
                prompt + f"\n\nIMPORTANT: Your previous draft was too long. "
                         f"Rewrite it to be UNDER {char_limit} characters. Count carefully."
            )

        message = _strip_em_dashes(message)
        logger.info("Generated %s message for %s (%d chars)", stage, lead.full_name, len(message))
        return message.strip()

    def generate_inmail(
        self,
        lead: Lead,
        template: str,
        brand: BrandConfig,
        prior_messages: Optional[list[str]] = None,
    ) -> tuple[str, str]:
        """Returns (subject, body) tuple for a Sales Navigator InMail."""
        prompt = build_prompt(
            stage="inmail",
            lead=lead,
            template=template,
            cta_url=brand.cta_url,
            cta_type=brand.cta_type,
            brand_name=brand.name,
            brand_description=brand.description,
            brand_value_prop=brand.value_prop,
            brand_voice_notes=brand.voice_notes,
            prior_messages=prior_messages,
        )

        raw = self._call_api(prompt)

        # Parse SUBJECT: / body format
        subject = ""
        body = raw.strip()
        lines = raw.strip().splitlines()
        for i, line in enumerate(lines):
            if line.upper().startswith("SUBJECT:"):
                subject = line[8:].strip()[:60]
                body = "\n".join(lines[i+1:]).strip()
                break

        if not subject:
            subject = f"Fellow believer in {lead.title or 'marketing'}"

        subject = _strip_em_dashes(subject)
        body = _strip_em_dashes(body)
        logger.info("Generated InMail for %s — subject: %s (%d chars), body: %d chars",
                    lead.full_name, subject, len(subject), len(body))
        return subject, body

    def generate_voice_script(self, lead: Lead, brand: BrandConfig) -> str:
        """Generate a 60-75 word voice note script for Andrew to record and send from mobile."""
        prompt = build_voice_memo_prompt(
            lead=lead,
            brand_name=brand.name,
            brand_description=brand.description,
            brand_voice_notes=brand.voice_notes,
        )
        script = self._call_api(prompt, max_tokens=250)
        script = _strip_em_dashes(script).strip()
        if len(script) > VOICE_MEMO_CHAR_LIMIT:
            logger.warning(
                "Voice script (%d chars) exceeds limit. Retrying with explicit constraint.",
                len(script),
            )
            script = self._call_api(
                prompt + f"\n\nIMPORTANT: Your draft was too long. Rewrite it under "
                         f"{VOICE_MEMO_CHAR_LIMIT} characters. Count every word.",
                max_tokens=250,
            )
            script = _strip_em_dashes(script).strip()
        logger.info("Generated voice script for %s (%d chars)", lead.full_name, len(script))
        return script

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
    def _call_api(self, user_prompt: str, max_tokens: int = 600) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
