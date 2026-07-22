"""Telegram publisher — raw Bot API, no library dependency."""

import logging
import os

import requests

logger = logging.getLogger("snowball.pub.telegram")

MAX_TELEGRAM_MSG = 4096


def esc(text) -> str:
    """Escape MarkdownV2 special chars."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


def split_long_message(text: str, max_len: int = MAX_TELEGRAM_MSG) -> list:
    """Split long messages at natural breakpoints (never exceed 4096)."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text[:max_len].rfind("\n")
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


def send(chat_id: str, text: str, silent: bool = False,
          preview: bool = False) -> bool:
    """Send a MarkdownV2 message. Returns True if all chunks delivered."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    ok_all = True
    for chunk in split_long_message(text):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "MarkdownV2",
                    "disable_web_page_preview": not preview,
                    "disable_notification": silent,
                },
                timeout=30,
            )
            if r.status_code != 200:
                logger.error(f"Telegram {r.status_code}: {r.text[:200]}")
                ok_all = False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            ok_all = False
    return ok_all


def alert_admin(text: str, silent: bool = True) -> bool:
    """Send to admin channel (anti-morte-silenziosa). No-op if unset."""
    admin = os.environ.get("CHANNEL_ADMIN")
    if not admin:
        return False
    return send(admin, text, silent=silent)
