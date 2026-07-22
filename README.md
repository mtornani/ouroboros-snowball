# ouroboros-snowball

Automazione minimale, effetto composto. Zero coinvolgimento a regime.

## Architettura canali (perché non solo Telegram)

Un canale Telegram pubblico da zero non cresce: Telegram non ha algoritmo né
ricerca. Quindi i ruoli sono separati:

| Canale | Ruolo | Perché |
|---|---|---|
| **X** | Discovery | La scouting-Twitter italiana è densa; le card di retrodizione con timestamp sono "receipts" nativamente quotabili |
| **Archivio SEO** (GitHub Pages) | Asset composto | Pagina timestampata che invecchia e aumenta di valore; prova pubblica verificabile |
| **Telegram privato** | Monetizzazione | Abbonamento Stars/Tribute, pagamenti a manutenzione zero |
| **Telegram pubblico** | Off di default | Attivalo in `config.json` solo quando avrai traffico da reindirizzare |

Il funnel: X/SEO → archivio (prova) → canale privato (cassa).

## Cosa gira, quando

| Job | Frequenza | Output |
|---|---|---|
| **Retrodizione** | ogni giorno 06:00 UTC | Card "segnalato N giorni prima" su X + archivio quando un flag storico compare in news di firme/convocazioni |
| **Digest** | lunedì 07:00 UTC | Teaser 3 nomi (X + archivio) + top 10 completo (Telegram privato) |

Vincoli cablati nel codice:
- "OB1" non compare mai in output pubblico (patto K-Sport).
- `excluded_competitions` (Serie C / Lega Pro = perimetro pilota) filtrate da ogni output pubblico.
- Fallimenti → alert su CHANNEL_ADMIN + `heartbeat.jsonl` (coerente con Blocco 1 anti-morte-silenziosa).

## Setup una tantum (~45 min totali)

**1. Repo (2 min):** crea `ouroboros-snowball` su GitHub, poi:
```bash
cd ouroboros-snowball
git remote add origin git@github.com:mtornani/ouroboros-snowball.git
git push -u origin main
```
Settings → Pages → Source: branch `main`, cartella `/docs`.
L'archivio sarà su `mtornani.github.io/ouroboros-snowball/radar/`
(più avanti puoi puntarci un sottodominio di matchanalysispro).

**2. Telegram (5 min):** crea il canale privato, aggiungi il bot esistente
come admin, attiva abbonamento con Telegram Stars (Gestione canale →
Abbonamento) oppure Tribute. Da qui i pagamenti si gestiscono da soli.

**3. X (10 min):** developer.x.com → account gratuito → app → genera
API Key/Secret + Access Token/Secret (permessi Read & Write).
Il free tier basta: ~40 post/mese.

**4. GitHub Secrets:** `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`,
`CHANNEL_PRIVATE`, `CHANNEL_ADMIN`, `X_API_KEY`, `X_API_SECRET`,
`X_ACCESS_TOKEN`, `X_ACCESS_SECRET`.
(`CHANNEL_PUBLIC` solo se attivi il mirror Telegram pubblico.)

**5. Claude Code (un prompt):**
```
CAVEMAN MODE. Repo ouroboros-snowball.

Task: collegare gli script allo schema reale.
1. Leggi scripts/snowball_digest.py e scripts/snowball_retrodiction.py.
2. Sostituisci i punti marcati ADAPT: mappa le query SQL sullo schema
   Neon reale usato da discovery_engine.py (tabella flag giocatori,
   campi nome/club/league/score/score_breakdown/fetched_at).
3. Non toccare: publishers/, escaping MarkdownV2, excluded_competitions,
   brand pubblico, heartbeat, dedup ledger.
4. Test in dry-run (stampa invece di inviare), poi commit.
Surgical changes only.
```

**6. Test:** Actions → Snowball → Run workflow. Se X e archivio si
aggiornano, hai finito. Per sempre.

## Coinvolgimento dopo il setup

Niente. Opzionale quando capita: repost manuale di un hit forte su
LinkedIn/WhatsApp. Il sistema gira anche senza.

## Aspettative oneste

Anche su X, da zero, i primi mesi sono lenti. I momenti di crescita sono
gli hit di retrodizione: ogni hit è marketing verificabile che si genera
da solo. L'archivio compone: più il sistema invecchia, più vale.
Cassa: decine di euro/mese all'inizio — ma ricorrente, e senza di te.
