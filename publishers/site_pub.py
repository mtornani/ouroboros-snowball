"""Site publisher — timestamped public archive on GitHub Pages.

Source of truth: docs/radar/cards.json (append-only).
Each publish regenerates docs/radar/index.html with data EMBEDDED
(offline-first standard: no fetch(), no CDN, single file, dark mode).

The archive is the compounding asset: verifiable timestamps + SEO long tail.
"""

import html
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("snowball.pub.site")

BASE = Path(__file__).parent.parent
CARDS_PATH = BASE / "docs" / "radar" / "cards.json"
INDEX_PATH = BASE / "docs" / "radar" / "index.html"


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Archivio del radar | Mirko Tornani</title>
<meta name="description" content="Archivio pubblico e datato delle segnalazioni del radar di Mirko Tornani: scouting a bassa visibilità da fonti pubbliche.">
<link rel="canonical" href="https://mtornani.github.io/ouroboros-snowball/radar/">
<style>
*, *::before, *::after {{ box-sizing:border-box; margin:0; padding:0; }}
:root {{ --ink:#1c1c1c; --muted:#5a5a5a; --line:#dcdcd6; --bg:#fafaf7; --accent:#1f5f4a;
    --sans:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }}
body {{ background:var(--bg); color:var(--ink); font:18px/1.65 Georgia,"Times New Roman",serif; }}
.wrap {{ max-width:720px; margin:0 auto; padding:0 24px; }}
header {{ border-bottom:1px solid var(--line); font:15px/1 var(--sans); }}
header .wrap {{ display:flex; justify-content:space-between; padding-top:20px; padding-bottom:20px; }}
header a {{ color:var(--ink); text-decoration:none; font-weight:600; }}
.kicker {{ font:600 13px/1.4 var(--sans); color:var(--muted); margin:64px 0 12px; }}
h1 {{ font-size:2.1rem; line-height:1.25; font-weight:normal; margin-bottom:20px; }}
.lead {{ color:var(--muted); font-size:1.05rem; margin-bottom:12px; }}
.note {{ font:14px/1.5 var(--sans); color:var(--muted); border-left:2px solid var(--accent); padding-left:14px; margin:20px 0 40px; }}
.entry {{ border-top:1px solid var(--line); padding:20px 0; }}
.meta {{ font:600 12px/1.4 var(--sans); letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin-bottom:6px; }}
.meta .k {{ color:var(--accent); }}
.entry h2 {{ font:600 17px/1.4 var(--sans); margin-bottom:4px; }}
.entry p {{ font-size:16px; }}
a {{ color:var(--accent); }}
.src {{ font:14px var(--sans); margin-top:6px; }}
footer {{ border-top:1px solid var(--line); margin-top:56px; padding:28px 0 48px; font:14px var(--sans); color:var(--muted); }}
footer a {{ color:var(--muted); }}
@media (max-width:600px) {{ body {{ font-size:17px; }} h1 {{ font-size:1.6rem; }} .kicker {{ margin-top:44px; }} }}
</style>
</head>
<body>
<header><div class="wrap"><a href="https://www.matchanalysispro.online/">Mirko Tornani</a><span style="color:var(--muted)">agg. {generated_at}</span></div></header>
<main class="wrap">
  <p class="kicker">Archivio pubblico</p>
  <h1>Il radar: segnalazioni datate, da controllare dopo</h1>
  <p class="lead">Ogni voce riporta la data in cui è stata pubblicata qui. Quando una notizia pubblica successiva riguarda lo stesso nome, è indicata con il link alla fonte, così chiunque può controllare.</p>
  <p class="note">Le segnalazioni non sono previsioni né raccomandazioni di mercato. Servono a orientare l'attenzione; la valutazione resta a chi guarda le partite.</p>
  <div id="cards"></div>
</main>
<footer><div class="wrap">Mirko Tornani &middot; <a href="https://www.matchanalysispro.online/">matchanalysispro.online</a> &middot; <a href="mailto:mirkotornani@gmail.com">mirkotornani@gmail.com</a></div></footer>
<script>
const CARDS = {cards_json};
function render() {{
    const el = document.getElementById('cards');
    el.innerHTML = CARDS.map(c => `
      <article class="entry">
        <p class="meta"><span class="k">${{c.kind === 'hit' ? 'Riscontro' : 'Radar settimanale'}}</span> &middot; ${{c.date}}</p>
        <h2>${{c.title}}</h2>
        <p>${{c.body}}</p>
        ${{c.source_url ? `<p class="src"><a href="${{c.source_url}}"
         target="_blank" rel="noopener">Fonte esterna</a></p>` : ''}}
      </article>`).join('');
}}
document.addEventListener('DOMContentLoaded', render);
</script>
</body>
</html>
"""


def _load_cards() -> list:
    if CARDS_PATH.exists():
        return json.loads(CARDS_PATH.read_text(encoding="utf-8"))
    return []


def _render_page(cards: list, config: dict) -> str:
    """Render the archive page.

    Policy: no lead-day / "anticipo" claims are published. Past-prediction
    claims require a verifiable date plus a public source; estimated lead
    days are stripped from the public output.
    """
    hits = [c for c in cards if c.get("kind") == "hit"]
    public_cards = [{k: v for k, v in c.items() if k != "lead_days"}
                    for c in cards]
    return PAGE_TEMPLATE.format(
        brand=html.escape(config.get("public_brand", "Ouroboros Radar")),
        generated_at=datetime.utcnow().strftime("%d/%m/%Y"),
        n_hits=len(hits),
        site_url=html.escape(config.get("site_url", "")),
        cards_json=json.dumps(public_cards, ensure_ascii=False),
    )


def regenerate(config: dict) -> bool:
    INDEX_PATH.write_text(_render_page(_load_cards(), config), encoding="utf-8")
    return True


def publish(kind: str, title: str, body: str, config: dict,
            lead_days: int = None, source_url: str = None) -> bool:
    """Append a card and regenerate the archive page. Newest first."""
    try:
        cards = _load_cards()
        cards.insert(0, {
            "kind": kind,  # "hit" | "digest"
            "title": html.escape(title),
            "body": html.escape(body),
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "lead_days": None,  # estimates never written to public cards.json
            "source_url": source_url,  # rendered as attribute, trusted RSS link
        })
        for c in cards:
            c["lead_days"] = None
        cards = cards[:200]  # keep page light

        CARDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        CARDS_PATH.write_text(
            json.dumps(cards, ensure_ascii=False, indent=2),
            encoding="utf-8")

        page = _render_page(cards, config)
        INDEX_PATH.write_text(page, encoding="utf-8")
        logger.info(f"Archive updated: {len(cards)} cards → {INDEX_PATH}")
        return True
    except Exception as e:
        logger.error(f"Site publish failed: {e}")
        return False
