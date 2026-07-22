#!/usr/bin/env python3
"""
SNOWBALL RETRODICTION — Daily credibility engine.

Flow: FETCH news → CACHE → CLEAN → MATCH vs historical flags → PUBLISH.

Publish targets (config["channels"]):
    x                  → discovery (scouting-Twitter, quotable receipts)
    site               → SEO archive (compounding asset, GitHub Pages)
    telegram_public    → optional mirror

Hard constraints: no "OB1" in public output; pilot perimeter excluded.
"""

import hashlib
import json
import logging
import os
import re
import time
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests
from fuzzywuzzy import fuzz
from unidecode import unidecode

sys.path.insert(0, str(Path(__file__).parent.parent))
from publishers import telegram_pub, x_pub, site_pub    # noqa: E402
from publishers.telegram_pub import esc                 # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("snowball.retro")

BASE = Path(__file__).parent.parent
CONFIG_PATH = BASE / "config.json"
HEARTBEAT_PATH = BASE / "heartbeat.jsonl"
CACHE_DIR = BASE / "data" / "cache"
POSTED_PATH = BASE / "data" / "posted_hits.json"

# Mappa tier (schema reale discovery_engine.py) -> etichetta "league"
# leggibile. serie_c/serie_c_riserve confluiscono su "Serie C" apposta:
# e' il nome che config.json["excluded_competitions"] si aspetta di trovare
# per tenere fuori dal pubblico il perimetro pilota (K-Sport).
TIER_LEAGUE_LABELS = {
    "serie_c": "Serie C",
    "serie_c_riserve": "Serie C",
    "serie_d": "Serie D",
    "serie_d_riserve": "Serie D",
    "conmebol_u20": "CONMEBOL U20",
    "conmebol_u17": "CONMEBOL U17",
    "nationality_pool": "Pool nazionalità",
}


def _tier_to_league(tier) -> str:
    return TIER_LEAGUE_LABELS.get(tier, tier or "?")


# --------------------------------------------------------- fetch/cache ---

def cache_key(identifier: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(identifier.encode()).hexdigest()[:12]
    return CACHE_DIR / f"{h}.json"


def fetch_news(config: dict) -> list:
    """FETCH: Google News RSS for signing/call-up queries. Zero credentials."""
    items = []
    for q in config.get("retro_queries", []):
        key = cache_key(f"news:{q}:{datetime.utcnow():%Y%m%d}")
        if key.exists():
            items.extend(json.loads(key.read_text(encoding="utf-8")))
            continue
        url = ("https://news.google.com/rss/search?q="
               + requests.utils.quote(q) + "&hl=it&gl=IT&ceid=IT:it")
        try:
            time.sleep(2)  # rate limit
            resp = requests.get(url, timeout=30,
                                 headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            batch = [{
                "title": (it.findtext("title") or "").strip(),
                "url": (it.findtext("link") or "").strip(),
                "pub_date": (it.findtext("pubDate") or "").strip(),
                "query": q,
            } for it in root.iter("item")]
            key.write_text(json.dumps(batch, ensure_ascii=False, indent=2),
                            encoding="utf-8")
            items.extend(batch)
        except Exception as e:
            logger.warning(f"News fetch failed [{q}]: {e}")
    logger.info(f"Fetched {len(items)} news items")
    return items


def fetch_historical_flags() -> list:
    """
    All historical flags with first-seen timestamp.

    ADAPT (Claude Code): stesso store JSONB di fetch_week_top (radar_state,
    key='radar_feed') — non esiste una tabella "flagged_players" da fare
    GROUP BY. flagged_at = history[0]["run_at"], il run piu' vecchio ancora
    conservato per quel candidato. Limite onesto ereditato dallo schema
    upstream: discovery_engine.py tronca la history di ogni candidato alle
    ultime 30 run (vedi record["history"][-30:]), quindi per un candidato
    monitorato per moltissimi run il vero primo avvistamento puo' essere
    piu' antico di quanto qui riportato.
    Required fields: name, club, league, flagged_at.
    """
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT data FROM radar_state WHERE key = %s", ("radar_feed",))
            row = cur.fetchone()
    feed = row["data"] if row else {}

    rows = []
    for record in feed.values():
        history = record.get("history") or []
        if not history:
            continue
        identity = record.get("identity") or {}
        rows.append({
            "name": identity.get("name"),
            "club": identity.get("club"),
            "league": _tier_to_league(identity.get("tier")),
            "flagged_at": history[0]["run_at"],
        })
    logger.info(f"Loaded {len(rows)} historical flags")
    return rows


# --------------------------------------------------------------- match ---

SIGNING_WORDS = re.compile(
    r"\b(firma|ufficiale|acquist|ingaggi|trasferi|convocat|esordi|debutt|cedut)\w*",
    re.IGNORECASE,
)


def find_hits(news: list, flags: list, config: dict) -> list:
    """MATCH: fuzzy-match flag names inside signing/call-up headlines."""
    threshold = config.get("match_threshold", 88)
    min_lead_days = config.get("min_lead_days", 14)
    hits = []
    for item in news:
        title = item["title"]
        if not SIGNING_WORDS.search(title):
            continue
        title_norm = unidecode(title).lower()
        for flag in flags:
            name_norm = unidecode(flag["name"]).lower().strip()
            if len(name_norm) < 6:
                continue  # too short → false-positive risk
            if fuzz.partial_ratio(name_norm, title_norm) < threshold:
                continue
            flagged_at = flag["flagged_at"]
            if isinstance(flagged_at, str):
                flagged_at = datetime.fromisoformat(flagged_at)
            if flagged_at.tzinfo is None:
                flagged_at = flagged_at.replace(tzinfo=timezone.utc)
            lead_days = (datetime.now(timezone.utc) - flagged_at).days
            if lead_days < min_lead_days:
                continue
            hits.append({
                "player": flag["name"],
                "league": flag.get("league"),
                "flagged_at": flagged_at.isoformat(),
                "lead_days": lead_days,
                "news_title": title,
                "news_url": item["url"],
            })
    logger.info(f"Retrodiction hits: {len(hits)}")
    return hits


def dedup_hits(hits: list) -> list:
    """Never post the same (player, news_url) twice. Persistent ledger."""
    POSTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    posted = set()
    if POSTED_PATH.exists():
        posted = set(json.loads(POSTED_PATH.read_text(encoding="utf-8")))
    fresh = []
    for h in hits:
        key = hashlib.md5(f"{h['player']}|{h['news_url']}".encode()).hexdigest()
        if key not in posted:
            fresh.append(h)
            posted.add(key)
    POSTED_PATH.write_text(json.dumps(sorted(posted)), encoding="utf-8")
    return fresh


# ------------------------------------------------------------- compose ---

def compose_x(hit: dict, config: dict) -> str:
    """X card: <=280 chars, quotable. Niente URL nel testo (pricing X: post
    con link costano 13x pay-per-use) — l'archivio si richiama a parole."""
    weeks = hit["lead_days"] // 7
    lead = f"{weeks} settimane" if weeks >= 2 else f"{hit['lead_days']} giorni"
    return (
        f"🎯 {hit['player']} era nel nostro radar dal "
        f"{hit['flagged_at'][:10]}.\n"
        f"Oggi è notizia. Anticipo: {lead}.\n"
        f"Archivio timestampato: link in bio"
    )


def compose_telegram(hit: dict, config: dict) -> str:
    brand = config.get("public_brand", "Ouroboros Radar")
    weeks = hit["lead_days"] // 7
    lead = f"{weeks} settimane" if weeks >= 2 else f"{hit['lead_days']} giorni"
    return (
        f"🎯 *RETRODIZIONE* — {esc(brand)}\n\n"
        f"*{esc(hit['player'])}* era nel radar dal *{esc(hit['flagged_at'][:10])}*\\.\n"
        f"Oggi: {esc(hit['news_title'][:120])}\n\n"
        f"⏱ Anticipo: *{esc(lead)}*\\.\n"
        f"📎 [Fonte]({hit['news_url']})\n\n"
        f"_L'archivio timestampato è la prova\\._"
    )


# ---------------------------------------------------------------- main ---

def heartbeat(status: str, extra: dict = None):
    entry = {"ts": datetime.utcnow().isoformat(),
             "job": "snowball_retrodiction", "status": status, **(extra or {})}
    with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        channels = config.get("channels", {})
        excluded = config.get("excluded_competitions", [])

        news = fetch_news(config)
        flags = fetch_historical_flags()
        hits = dedup_hits(find_hits(news, flags, config))

        posted = 0
        for hit in hits[:config.get("max_hits_per_day", 2)]:
            # Pilot perimeter (K-Sport) never goes public
            if any(x.lower() in (hit.get("league") or "").lower() for x in excluded):
                logger.info(f"Hit in excluded perimeter, skipped: {hit['player']}")
                continue

            ok = []
            if channels.get("x", True):
                ok.append(x_pub.send(compose_x(hit, config)))
            if channels.get("site", True):
                ok.append(site_pub.publish(
                    kind="hit",
                    title=hit["player"],
                    body=f"Segnalato il {hit['flagged_at'][:10]}. "
                         f"Oggi: {hit['news_title'][:140]}",
                    config=config,
                    lead_days=hit["lead_days"],
                    source_url=hit["news_url"],
                ))
            if channels.get("telegram_public", False):
                ok.append(telegram_pub.send(
                    os.environ["CHANNEL_PUBLIC"],
                    compose_telegram(hit, config), preview=True))

            if any(ok):
                posted += 1
                telegram_pub.alert_admin(
                    f"🎯 Hit pubblicato: {esc(hit['player'])} "
                    f"\\({esc(str(hit['lead_days']))}gg\\)")

        heartbeat("ok", {"news": len(news), "hits": len(hits), "posted": posted})
        logger.info(f"Done: {posted} hit cards published")

    except Exception as e:
        logger.exception("Retrodiction failed")
        heartbeat("error", {"error": str(e)})
        telegram_pub.alert_admin(
            f"🚨 *Snowball retrodiction FAILED*\n{esc(str(e)[:500])}", silent=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
