import logging
from typing import Optional

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from ai.prompts import CHAR_LIMITS, SYSTEM_PROMPT, build_prompt
from config.settings import BrandConfig
from database.models import Lead

logger = logging.getLogger(__name__)


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
            brand_value_prop=brand.value_prop,
            prior_messages=prior_messages,
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

        logger.info("Generated %s message for %s (%d chars)", stage, lead.full_name, len(message))
        return message.strip()

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=30))
    def _call_api(self, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
