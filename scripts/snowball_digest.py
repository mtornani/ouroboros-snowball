#!/usr/bin/env python3
"""
SNOWBALL DIGEST — Weekly auto-digest.

Publish targets (config["channels"]):
    x                  → teaser (discovery)
    site               → teaser card in SEO archive
    telegram_public    → optional teaser mirror
    telegram_private   → FULL digest (paid subscribers — the cash-flow layer)

Hard constraints: no "OB1" in public output; pilot perimeter excluded
from everything public-facing.
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent))
from publishers import telegram_pub, x_pub, site_pub    # noqa: E402
from publishers.telegram_pub import esc                 # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("snowball.digest")

BASE = Path(__file__).parent.parent
CONFIG_PATH = BASE / "config.json"
HEARTBEAT_PATH = BASE / "heartbeat.jsonl"

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


# ---------------------------------------------------------------- data ---

def fetch_week_top(config: dict):
    """
    FETCH: top flagged players of the last 7 days.

    ADAPT (Claude Code): lo schema reale usato da discovery_engine.py NON e'
    una tabella relazionale "flagged_players" — e' un key-value store JSONB
    (radar_state(key TEXT PRIMARY KEY, data JSONB)), con key='radar_feed' e
    data = {candidate_id: {"identity": {...}, "history": [...]}}. Ogni voce
    di history e' uno snapshot di un run (run_at/signal_score/components).
    Si legge la riga JSONB una volta e si fa selezione/ordinamento in Python
    (non c'e' una tabella su cui scrivere un WHERE/ORDER BY reale).
    tier -> proxy di "league" (vedi TIER_LEAGUE_LABELS).
    Fields: name, position, club, league, score, score_breakdown, fetched_at.
    """
    since = datetime.now(timezone.utc) - timedelta(days=7)
    min_score = config.get("min_score", 40)

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
        last = history[-1]
        score = last.get("signal_score")
        if score is None or score < min_score:
            continue
        fetched_at = datetime.fromisoformat(last["run_at"])
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if fetched_at < since:
            continue
        identity = record.get("identity") or {}
        rows.append({
            "name": identity.get("name"),
            "position": identity.get("role"),
            "club": identity.get("club"),
            "league": _tier_to_league(identity.get("tier")),
            "score": score,
            "score_breakdown": last.get("components"),
            "fetched_at": fetched_at,
        })
    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:50]

    excluded = config.get("excluded_competitions", [])
    public_rows = [r for r in rows if not any(
        x.lower() in (r.get("league") or "").lower() for x in excluded)]
    logger.info(f"Fetched {len(rows)} flags, {len(public_rows)} public-eligible")
    return rows, public_rows


# ------------------------------------------------------------- compose ---

def compose_x_teaser(public_rows: list, config: dict) -> str:
    """X teaser: 3 names, <=280 chars. Niente URL nel testo (pricing X:
    post con link costano 13x pay-per-use) — l'archivio si richiama a parole."""
    names = " · ".join(
        f"{p['name']} ({p.get('club') or '?'})" for p in public_rows[:3])
    return (
        f"🐍 Radar settimanale — 3 dei {len(public_rows)} nomi di questa "
        f"settimana:\n{names}\n"
        f"Lista completa e note sul canale riservato. "
        f"Archivio timestampato: link in bio"
    )


def compose_tg_teaser(public_rows: list, config: dict) -> str:
    brand = config.get("public_brand", "Ouroboros Radar")
    today = datetime.now().strftime("%d/%m/%Y")
    header = f"🐍 *{esc(brand)}* — Radar settimanale\n_{esc(today)}_\n\n"
    body = "".join(
        f"{i}\\. *{esc(p['name'])}* \\({esc(p.get('position') or '?')}\\) — "
        f"{esc(p.get('club') or '?')}\n"
        for i, p in enumerate(public_rows[:3], 1))
    footer = (
        f"\n📡 Radar completo \\({esc(str(len(public_rows)))} nomi\\) "
        f"sul canale riservato\\.\n"
        f"⏱ Ogni segnalazione è timestampata\\. L'archivio è la prova\\."
    )
    return header + body + footer


def compose_full(rows: list, public_rows: list, config: dict) -> str:
    """Private full digest: top 10 with score + strongest pattern note."""
    today = datetime.now().strftime("%d/%m/%Y")
    header = (f"📋 *Radar Completo* — settimana {esc(today)}\n"
              f"_{esc(str(len(rows)))} segnalazioni totali_\n"
              f"{esc('─' * 20)}\n\n")
    body = ""
    for i, p in enumerate(public_rows[:10], 1):
        emoji = "🟢" if p["score"] >= 70 else "🟡" if p["score"] >= 40 else "🔴"
        score_txt = f"{p['score']:.0f}"
        body += (f"{i}\\. {emoji} *{esc(p['name'])}* "
                 f"\\({esc(p.get('position') or '?')}\\) — "
                 f"{esc(p.get('club') or '?')}, {esc(p.get('league') or '?')}\n"
                 f"   Score: *{esc(score_txt)}*")
        breakdown = p.get("score_breakdown") or {}
        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except Exception:
                breakdown = {}
        if breakdown:
            top_pattern = max(breakdown, key=breakdown.get)
            body += f" · {esc(top_pattern[:40])}"
        body += "\n\n"
    return header + body


# ---------------------------------------------------------------- main ---

def heartbeat(status: str, extra: dict = None):
    entry = {"ts": datetime.utcnow().isoformat(),
             "job": "snowball_digest", "status": status, **(extra or {})}
    with open(HEARTBEAT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        channels = config.get("channels", {})
        rows, public_rows = fetch_week_top(config)

        if not public_rows:
            logger.info("Empty week — no post")
            heartbeat("ok_empty")
            telegram_pub.alert_admin(esc("Digest: settimana vuota, nessun post."))
            return

        results = {}
        if channels.get("x", True):
            results["x"] = x_pub.send(compose_x_teaser(public_rows, config))
        if channels.get("site", True):
            names = ", ".join(p["name"] for p in public_rows[:3])
            results["site"] = site_pub.publish(
                kind="digest",
                title=f"Radar settimanale — {len(public_rows)} nomi",
                body=f"In evidenza: {names}. Lista completa sul canale riservato.",
                config=config)
        if channels.get("telegram_public", False):
            results["tg_pub"] = telegram_pub.send(
                os.environ["CHANNEL_PUBLIC"],
                compose_tg_teaser(public_rows, config))
        if channels.get("telegram_private", True):
            results["tg_priv"] = telegram_pub.send(
                os.environ["CHANNEL_PRIVATE"],
                compose_full(rows, public_rows, config))

        heartbeat("ok" if all(results.values()) else "partial",
                   {"public": len(public_rows), "total": len(rows), **results})
        logger.info(f"Digest published: {results}")

    except Exception as e:
        logger.exception("Digest failed")
        heartbeat("error", {"error": str(e)})
        telegram_pub.alert_admin(
            f"🚨 *Snowball digest FAILED*\n{esc(str(e)[:500])}", silent=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
