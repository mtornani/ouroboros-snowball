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
<title>{brand} • Archivio Radar</title>
<meta name="description" content="Archivio timestampato delle segnalazioni {brand}: ogni nome ha una data verificabile, prima della notizia.">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
    --bg-primary:#0f1117; --bg-card:#1a1d28; --bg-elevated:#242736;
    --text-primary:#e8e8ed; --text-secondary:#9a9ab0; --text-muted:#6b6b80;
    --accent:#667eea; --accent-hover:#7c94f6;
    --success:#34d399; --warning:#fbbf24; --danger:#f87171;
    --border:#2a2d3a;
    --space-xs:4px; --space-sm:8px; --space-md:16px; --space-lg:24px;
    --font:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    --font-mono:'SF Mono','Fira Code',monospace;
    --text-sm:13px; --text-base:15px; --text-lg:18px; --text-xl:24px; --text-2xl:32px;
    --radius:8px; --radius-lg:12px; --max-width:760px;
}}
body {{ font-family:var(--font); background:var(--bg-primary); color:var(--text-primary);
    font-size:var(--text-base); line-height:1.6; min-height:100vh;
    -webkit-font-smoothing:antialiased; }}
.container {{ max-width:var(--max-width); margin:0 auto; padding:var(--space-md); }}
.header {{ background:var(--bg-card); padding:var(--space-md);
    border-bottom:1px solid var(--border); position:sticky; top:0; z-index:100; }}
.header-content {{ display:flex; justify-content:space-between; align-items:center;
    max-width:var(--max-width); margin:0 auto; }}
.logo {{ font-size:var(--text-xl); font-weight:800;
    background:linear-gradient(135deg,var(--accent),#a78bfa);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
.card {{ background:var(--bg-card); border:1px solid var(--border);
    border-radius:var(--radius-lg); padding:var(--space-lg);
    margin-bottom:var(--space-md); transition:border-color .2s; }}
.card:hover {{ border-color:var(--accent); }}
.card-title {{ font-size:var(--text-lg); font-weight:700; margin-bottom:var(--space-sm); }}
.badge {{ display:inline-block; font-size:var(--text-sm); font-weight:700;
    padding:2px 10px; border-radius:12px; margin-bottom:var(--space-sm); }}
.badge-hit {{ background:rgba(52,211,153,.15); color:var(--success); }}
.badge-digest {{ background:rgba(102,126,234,.15); color:var(--accent); }}
.text-muted {{ color:var(--text-muted); }}
.text-accent {{ color:var(--accent); }}
.font-mono {{ font-family:var(--font-mono); }}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ color:var(--accent-hover); }}
.stats-row {{ display:grid; grid-template-columns:repeat(2,1fr);
    gap:var(--space-md); margin-bottom:var(--space-lg); }}
.stat {{ background:var(--bg-card); border:1px solid var(--border);
    border-radius:var(--radius); padding:var(--space-md); text-align:center; }}
.stat-value {{ font-size:var(--text-2xl); font-weight:800; color:var(--accent); }}
.stat-label {{ font-size:var(--text-sm); color:var(--text-muted); margin-top:var(--space-xs); }}
@media (max-width:768px) {{
    :root {{ --text-base:14px; --text-xl:20px; --text-2xl:26px; --space-lg:16px; }}
}}
</style>
</head>
<body>
<div class="header"><div class="header-content">
  <div class="logo">{brand}</div>
  <div class="text-muted" style="font-size:12px">agg. {generated_at}</div>
</div></div>
<div class="container">
  <p class="text-muted" style="margin:var(--space-md) 0 var(--space-lg)">
    Ogni segnalazione qui sotto ha una data. La data viene prima della notizia.
    Non prevediamo: prioritizziamo l'attenzione. L'archivio &egrave; la prova.
  </p>
  <div class="stats-row">
    <div class="stat"><div class="stat-value">{n_hits}</div>
        <div class="stat-label">Retrodizioni</div></div>
    <div class="stat"><div class="stat-value">{avg_lead}</div>
        <div class="stat-label">Anticipo medio (gg)</div></div>
  </div>
  <div id="cards"></div>
  <p class="text-muted" style="margin-top:var(--space-lg);font-size:var(--text-sm)">
    Radar completo settimanale sul canale riservato &middot;
    <a href="{site_url}">{site_url}</a>
  </p>
</div>
<script>
const CARDS = {cards_json};
function render() {{
    const el = document.getElementById('cards');
    el.innerHTML = CARDS.map(c => `
      <div class="card">
        <span class="badge badge-${{c.kind === 'hit' ? 'hit' : 'digest'}}">
         ${{c.kind === 'hit' ? 'RETRODIZIONE' : 'RADAR'}}</span>
        <div class="card-title">${{c.title}}</div>
        <p>${{c.body}}</p>
        <p class="text-muted font-mono" style="font-size:12px;margin-top:8px">
         ${{c.date}}${{c.lead_days ? ' · anticipo ' + c.lead_days + ' giorni' : ''}}
        </p>
        ${{c.source_url ? `<p style="margin-top:4px"><a href="${{c.source_url}}"
         target="_blank" rel="noopener">Fonte esterna</a></p>` : ''}}
      </div>`).join('');
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
            "lead_days": lead_days,
            "source_url": source_url,  # rendered as attribute, trusted RSS link
        })
        cards = cards[:200]  # keep page light

        CARDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        CARDS_PATH.write_text(
            json.dumps(cards, ensure_ascii=False, indent=2),
            encoding="utf-8")

        hits = [c for c in cards if c["kind"] == "hit" and c.get("lead_days")]
        avg_lead = round(sum(c["lead_days"] for c in hits) / len(hits)) if hits else 0

        page = PAGE_TEMPLATE.format(
            brand=html.escape(config.get("public_brand", "Ouroboros Radar")),
            generated_at=datetime.utcnow().strftime("%d/%m/%Y"),
            n_hits=len(hits),
            avg_lead=avg_lead,
            site_url=html.escape(config.get("site_url", "")),
            cards_json=json.dumps(cards, ensure_ascii=False),
        )
        INDEX_PATH.write_text(page, encoding="utf-8")
        logger.info(f"Archive updated: {len(cards)} cards → {INDEX_PATH}")
        return True
    except Exception as e:
        logger.error(f"Site publish failed: {e}")
        return False
