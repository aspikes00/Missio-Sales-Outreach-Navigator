from __future__ import annotations
from database.models import Lead

SYSTEM_PROMPT = """\
You write LinkedIn outreach messages for a B2B sales professional who follows the Sandler Sales System.

SANDLER RULES — follow all of them without exception:
1. Open with a genuine, SPECIFIC compliment tied to something real in the lead's profile
   (a post they wrote, their headline, a company milestone). Never use generic praise.
2. Frame a relevant pain point BEFORE presenting any value. The prospect must feel understood first.
3. Use mutual fit language — "not sure if this is right for you", "may not be relevant" —
   to lower resistance and signal respect for their time.
4. Use a SOFT call-to-action only. Never say "book a call", never use urgency language, never oversell.
5. Sound like a real person — conversational, direct, no corporate jargon, no buzzwords.
6. SHORT messages. LinkedIn is not email. Keep every message tight.
7. NEVER use "building", "growing", "founding", "running your own", or other owner/founder
   language unless the lead's title explicitly says Founder, Co-Founder, CEO, Owner, or Principal.
   A VP, Director, or Manager works INSIDE a company — they are not building it. Use their
   actual title to frame any reference to their work (e.g. "your work in marketing at X", not
   "what you're building at X").

OUTPUT FORMAT:
- Return ONLY the message text, ready to paste into LinkedIn
- No subject line, no label, no explanation, no extra commentary
- Preserve the paragraph breaks from the template structure
"""

CHAR_LIMITS = {
    "connection_note": 300,
    "message_1": 1000,
    "message_2": 800,
    "message_3": 700,
    "message_4": 700,
    "message_5": 600,
    "inmail_subject": 60,
    "inmail_body": 600,
}

_CTA_INSTRUCTIONS = {
    "discovery_call": (
        "The call-to-action is a short discovery call. "
        "Use soft language: 'worth a quick 20 minutes?', 'would it make sense to chat?'. "
        "Include the Calendly link naturally — as an option, not a demand."
    ),
    "free_trial": (
        "The call-to-action is a free trial signup — no sales call needed. "
        "Position it as low-commitment: 'free to try', 'no obligation', 'see it yourself'. "
        "Include the signup link naturally — frame it as an easy next step if the pain resonates."
    ),
    "calculator": (
        "The call-to-action is a free marketing calculator they can use on their own time — no call required. "
        "Frame it as a useful tool, not a lead generation step: 'built a calculator that shows what this looks like in your own numbers.' "
        "Include the calculator URL on its own line — clean and visible, not buried in a sentence. "
        "Never mention booking a call or Calendly. The calculator IS the entire ask."
    ),
}

STAGE_INSTRUCTIONS = {
    "inmail": (
        "Write a LinkedIn Sales Navigator InMail message. "
        "Return your response in exactly this format:\n"
        "SUBJECT: [subject line, max 60 chars]\n\n[body text, max 600 chars]\n\n"
        "The subject must reference something specific from their profile. "
        "The body: peer opener (agency owner) → specific profile hook → one pain question → mutual fit close. "
        "No Calendly link, no meeting ask — the only goal is a reply."
    ),
    "connection_note": (
        "Write a LinkedIn connection request note. "
        "HARD LIMIT: {char_limit} characters (LinkedIn enforces this — count carefully). "
        "Start with a specific compliment. End with a brief, soft reason to connect. "
        "No ask yet — just earn the connection."
    ),
    "message_1": (
        "Write the first message AFTER the connection was accepted (3–5 days later). "
        "Thank them briefly for connecting. "
        "Ask ONE pain-point discovery question relevant to their role and company. "
        "Then reference a common challenge you see for people in their position. "
        "Use mutual fit language — you're NOT sure if this is relevant for them specifically. "
        "No CTA in this message."
    ),
    "message_2": (
        "Write a follow-up to message 1 (no reply received, 5–6 days later). "
        "Brief re-engagement — acknowledge it may have gotten buried. "
        "Offer a single sentence of value connecting the pain point to an outcome. "
        "End with a very soft ask: 'worth a quick conversation, or not the right timing?'"
    ),
    "message_3": (
        "Write the third message in the sequence (no reply to message 2, 5–6 days later). "
        "This is NOT the final message — do not use break-off language like 'last note from me.' "
        "Drop the calculator link cleanly. Keep it brief and low-pressure. "
        "{cta_instruction} "
        "Close warmly but leave room for the conversation to continue."
    ),
    "message_4": (
        "Write the fourth message (no reply to message 3, 5–6 days later). "
        "Acknowledge the calculator may not be relevant if they don't run paid ads — don't assume. "
        "Pivot to the real value: a brief informal conversation between two people in the same world. "
        "Use equal-status language — you're not asking them to do you a favor, you're offering a genuine exchange. "
        "The tone should feel like a coffee chat invite, not a sales discovery call. "
        "{cta_instruction} "
        "Close with a soft out — 'totally fine if not the right time.'"
    ),
    "message_5": (
        "Write the final message in the sequence (no reply to message 4, 5–6 days later). "
        "Clean Sandler break-off — honest, no guilt, no desperation. "
        "One line restating the offer: a quick informal conversation, no agenda. "
        "{cta_instruction} "
        "Close warmly and leave the door permanently open — 'if timing ever changes.' "
        "This should feel like a gracious exit from someone confident enough to walk away."
    ),
}


def build_prompt(
    stage: str,
    lead: Lead,
    template: str,
    cta_url: str,
    cta_type: str,
    brand_name: str,
    brand_description: str,
    brand_value_prop: str,
    brand_voice_notes: str,
    prior_messages: list[str] | None = None,
    calendly_url: str = "",
) -> str:
    char_limit = CHAR_LIMITS.get(stage, 1000)
    # Messages 4 and 5 push toward the Calendly booking — use discovery_call CTA instructions
    effective_cta_type = "discovery_call" if stage in ("message_4", "message_5") else cta_type
    effective_cta_url = calendly_url if stage in ("message_4", "message_5") and calendly_url else cta_url
    cta_instruction = _CTA_INSTRUCTIONS.get(effective_cta_type, _CTA_INSTRUCTIONS["discovery_call"])

    stage_instruction = STAGE_INSTRUCTIONS[stage].format(
        char_limit=char_limit,
        cta_instruction=cta_instruction,
    )

    active_cta_url = effective_cta_url

    posts_block = ""
    if lead.recent_posts:
        posts_block = "\n".join(
            f"Recent post {i+1}: {post}" for i, post in enumerate(lead.recent_posts)
        )
    else:
        posts_block = "Recent posts: (none available — use headline and title for personalization)"

    prior_block = ""
    if prior_messages:
        prior_block = (
            "\nPRIOR MESSAGES SENT TO THIS LEAD (do not repeat these ideas or phrases):\n"
            + "\n---\n".join(prior_messages)
        )

    voice_block = f"\nVOICE & STYLE RULES FOR THIS BRAND:\n{brand_voice_notes}" if brand_voice_notes else ""

    return f"""\
STAGE: {stage}
INSTRUCTION: {stage_instruction}

SENDER'S BRAND CONTEXT (awareness only — do not copy-paste into the message):
Brand: {brand_name}
Who we are: {brand_description}
What we produce: {brand_value_prop}
CTA type: {effective_cta_type}
CTA URL: {active_cta_url}
{voice_block}

LEAD PROFILE:
Name: {lead.full_name or lead.first_name}
First name: {lead.first_name}
Title: {lead.title or "(unknown)"}
Company: {lead.company_name or "(unknown)"}
Industry: {lead.industry or "(unknown)"}
Location: {lead.location or "(unknown)"}
LinkedIn headline: {lead.headline or "(none)"}
About (excerpt): {lead.about_snippet or "(none)"}
{posts_block}

TONE & STRUCTURE GUIDE (follow this template's voice, structure, and key rules exactly):
{template}
{prior_block}

Write the message now:"""
