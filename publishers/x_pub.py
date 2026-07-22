"""X (Twitter) publisher — API v2, OAuth 1.0a user context.

Free tier is enough: ~1 retro card/day + 1 digest/week ≈ 35-40 posts/month.
If keys are missing, publishing is skipped gracefully (never crashes the job).

Env vars: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
"""

import logging
import os

from requests_oauthlib import OAuth1Session

logger = logging.getLogger("snowball.pub.x")

MAX_X_CHARS = 280


def is_configured() -> bool:
    return all(os.environ.get(k) for k in (
        "X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"))


def send(text: str) -> bool:
    """Post a tweet. Truncates safely at 280 chars. Returns True on success."""
    if not is_configured():
        logger.info("X keys not configured — skipping X publish")
        return False
    if len(text) > MAX_X_CHARS:
        text = text[: MAX_X_CHARS - 1] + "…"
    try:
        oauth = OAuth1Session(
            os.environ["X_API_KEY"],
            client_secret=os.environ["X_API_SECRET"],
            resource_owner_key=os.environ["X_ACCESS_TOKEN"],
            resource_owner_secret=os.environ["X_ACCESS_SECRET"],
        )
        r = oauth.post(
            "https://api.twitter.com/2/tweets",
            json={"text": text},
            timeout=30,
        )
        if r.status_code not in (200, 201):
            logger.error(f"X API {r.status_code}: {r.text[:200]}")
            return False
        logger.info("Posted to X")
        return True
    except Exception as e:
        logger.error(f"X publish failed: {e}")
        return False
