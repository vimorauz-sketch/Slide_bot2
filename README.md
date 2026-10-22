# SlideLab Telegram Bot

A Telegram bot (aiogram 3) that turns a topic into a designed presentation, Gamma-style:

1. **Plan first.** The AI drafts an outline (one line per slide, each with a chosen layout). The user
   approves it, asks for changes in plain words, or requests a different plan.
2. **Slide-by-slide writing.** Every slide is written in parallel against the JSON shape of its own
   layout (20 layouts: cards, process, cycle, timeline, stats, chart, comparison, pyramid, formula,
   table, quote, highlight, …), with an icon, a picture query and speaker notes.
3. **Real design engine.** Slides are HTML/CSS (Jinja2 templates + **400 different templates**: 1-200
   illustrated templates and **201-400 "Real foto" templates** that put real, topic-matched photos on the
   cover, on every card / step / list item and on most slides. Each
   with 10 contrast-checked colour sets: 20 hand-made design families and 180 generated designs that
   combine 31 art styles, 12 cover compositions, 31 font pairs, backgrounds, card, heading, icon,
   picture-frame and decoration styles) rendered by Chromium. Every deck also gets **subject
   stickers** (90 illustrations: biology, chemistry, maths, history, IT, economics, medicine, art…)
   picked from its subject and drawn in the template's own sticker style (die-cut, 3D, riso, line,
   glass, badge, doodle, flat, mono)
   (Playwright). Text is auto-fitted (shrinks or grows, then trims as a last resort), photos come
   from Pexels / Unsplash / Wikimedia / OpenAI images, and every theme has its own generated
   illustrations when no photo is available.
4. **Template gallery Mini App.** A Telegram Mini App (`webapp/`) to browse all 200 templates by
   category, search them, swipe through real slide previews and pick one of the colour sets. Without an HTTPS URL
   the same catalogue is browsable with inline buttons (category → style → colour).
5. **Outputs from one source.** JPEG previews (watermarked), PDF, and an **editable PPTX**
   (rendered background + native PowerPoint text boxes at the exact positions, notes included).

```
services/
  ai_service.py        outline -> per-slide content (OpenAI); mock generator without a key
  presentation.py      build_presentation(): content -> images -> render -> previews
  preview_service.py   watermark, preview selection, overview grid
  deck/
    catalog.py         the 20 layouts: fields, limits, normalization
    render.py          HTML build, auto-fit, PNG/JPEG, PDF, PPTX orchestration
    pptx_export.py     editable PPTX (background image + measured text boxes)
    images.py          Pexels / Unsplash / Wikimedia / OpenAI, disk cache
    art.py             per-theme generated illustrations (fallback pictures)
    charts.py          SVG charts, cycle and pyramid geometry
    text.py            Uzbek apostrophes (o‘ g‘ ’), quotes, typography
    templates/         base.css, deck/slide templates, layouts/*.j2
    palettes.py        OKLCH colour recipes + WCAG checks for the colour sets
    design_space.py    the dimensions/options of generated templates and the generator
    sticker_art.py     subject sticker drawings (colour roles) + subject keywords
    stickers.py        sticker styles, subject detection, per-slide sticker choice
    themes.py          200 templates + colour sets ("<id>~<colour>"), aliases, gallery catalogue
    templates/traits.css  design traits (tr-*) and cover compositions used by generated templates
services/gallery.py    preview images: static thumbs, on-demand colour previews, inline-gallery sheets
themes/<id>/           templates 1-20 (hand-made): theme.json (palette, fonts, art, recipe), theme.css, decor.j2
themes/templates.json  templates 21-200 + colour sets of all templates (scripts/generate_templates.py)
themes/overview.jpg    cover mosaic (first picker message)
webapp/                Mini App: index.html, catalog.json, thumbs/<theme>/<n>.webp
assets/fonts, icons    28 bundled font families (Latin, Latin-ext, Cyrillic) + 2100 Lucide icons
```

### Adding or changing a theme
Copy a folder in `themes/`, edit `theme.json` (palette, fonts from `assets/fonts/manifest.json`,
`art` style from `services/deck/art.py`, `cover_variant`, `pdf_mode`) and `theme.css` (CSS variables
plus any decoration — use only the base colour variables `--bg --bg2 --surface --text --muted
--primary --secondary --accent --on-primary --ink`, so colour variants work). Give it a `recipe`
(light / dark / cream) for its colour sets. Then:

```
python scripts/render_sample.py <theme_id>   # every layout as a contact sheet (storage/samples)
python scripts/generate_templates.py         # themes/templates.json (generated templates + colour sets)
python scripts/build_gallery.py              # Mini App previews, catalog.json, overview.jpg
```

### Photos
Photo search order: Pexels (`PEXELS_API_KEY`, free, best quality) → Pixabay (`PIXABAY_API_KEY`, free: sign in at pixabay.com and open pixabay.com/api/docs/, the key is shown there) → Unsplash (`UNSPLASH_ACCESS_KEY`) →
Openverse (no key) → Wikimedia Commons (no key). The AI writes an English photo query for every card and
step; photos are cached in `storage/image_cache`. Get a free Pexels key at https://www.pexels.com/api/ —
without it photos still work but are less consistent.

Previews of the photo templates are rendered by the bot server itself (they need real photos): on start a
background task renders all 200 covers (`GALLERY_WARMUP=0` turns it off), and other previews are rendered
on first view and cached in `storage/preview_cache`.

### Railway
The repo has a `Dockerfile` (Python + Chromium + fonts), which Railway uses automatically.
1. Variables: `BOT_TOKEN`, `OPENAI_API_KEY` (and optionally `PIXABAY_API_KEY` / `PEXELS_API_KEY`). Leave `WEBAPP_URL` empty.
2. Settings → Networking → **Generate Domain**. Railway then sets `RAILWAY_PUBLIC_DOMAIN`; the bot
   uses it as the Mini App address (`https://<domain>/webapp/`) and listens on Railway's `$PORT`.
3. For persistent data add a Volume mounted at `/app/storage` (and keep the SQLite DB there).

### Template gallery Mini App
`webapp/` is static. The bot's web server (`bot/webhook_app.py`, port `WEBHOOK_PORT`) serves it at
`/webapp/` together with `POST /webapp/api/select`, which checks Telegram's signed `initData`
before saving the user's choice. Telegram requires HTTPS:

1. Put the server behind HTTPS (nginx + certbot, or for testing `cloudflared tunnel --url http://localhost:8080`).
2. Set `WEBAPP_URL=https://your-domain/webapp/` in `.env` and restart the bot.
3. Optional: in @BotFather → *Bot Settings → Menu Button* set the same URL.

Previews of non-default colours are rendered on demand at `/webapp/preview/<key>/<n>.webp` and cached
in `storage/preview_cache/`. The bot then shows a **🎨 Dizayn laboratoriyasi** button (and a **🎨 Dizaynni tanlash** keyboard
button). Users can also simply type a template number (1–200).

## Requirements

- Python 3.10+ (developed and tested against 3.10.11)
- See `requirements.txt` for runtime dependencies (aiogram, SQLAlchemy + aiosqlite, Playwright, Jinja2, python-pptx,
  openai, pillow, pydantic-settings).
- See `requirements-dev.txt` for the test/lint toolchain (pytest, pytest-asyncio, pytest-cov,
  ruff).

## Setup

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
python -m playwright install chromium
# Linux servers also need Chromium's system libraries and the metric-compatible fonts
# used to size PPTX text (Liberation, Carlito, Caladea):
#   sudo python -m playwright install-deps chromium
#   sudo apt install fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea
```

Copy `.env.example` to `.env` and fill in your own values:

```bash
cp .env.example .env   # Windows: copy .env.example .env
```

For photos on slides add a free `PIXABAY_API_KEY` or `PEXELS_API_KEY` (and/or `UNSPLASH_ACCESS_KEY`); without keys the
themes' generated illustrations are used. Required for a real deployment: `BOT_TOKEN` (from @BotFather) and, optionally, `OPENAI_API_KEY`
(without it, the bot still works end-to-end using its built-in mock content generator).
`ADMIN_IDS` is a comma-separated list of Telegram user IDs allowed to use `/admin`; leaving it
empty denies admin access to everyone (fail-closed).

## Running the bot

```bash
# Windows
.venv\Scripts\python.exe main.py

# Linux / macOS
.venv/bin/python main.py
```

The bot polls Telegram (no webhook server); only one instance should run against a given bot
token at a time.

## Running tests

Install the dev dependencies first:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run the full suite:

```bash
# Windows
.venv\Scripts\python.exe -m pytest tests/

# Linux / macOS
.venv/bin/python -m pytest tests/
```

With coverage:

```bash
pytest tests/ --cov=bot --cov=services --cov=database --cov=config --cov-report=term-missing
```

Lint:

```bash
ruff check . --exclude .venv
```

Tests never touch the real `slidelab.db` or `storage/` directory, never call the real OpenAI or
Telegram APIs, and never send real messages — see `tests/conftest.py` and `tests/fixtures/` for
the isolation fixtures (an isolated SQLite DB per test, fake Telegram `Message`/`CallbackQuery`
objects, a fake OpenAI client).

```
tests/
  conftest.py          # shared fixtures (isolated DB, temp storage dir, fake Telegram objects)
  fixtures/            # reusable test doubles (DB factory, Telegram fakes, OpenAI fakes)
  unit/                # one module/handler under test per file
  integration/          # multi-component flows (wizard -> AI -> PPTX -> payment -> download)
```

## Deployment checklist

- `BOT_TOKEN` / `OPENAI_API_KEY` come from environment variables (`.env`, excluded from git via
  `.gitignore`) — never commit real secrets.
- Only **one** process should poll with a given `BOT_TOKEN` at a time (Telegram rejects
  concurrent `getUpdates` polling from the same token).
- `storage/` (orders, `image_cache/`, `art_cache/`) grows unboundedly today (generated `.pptx`/`.pdf`/preview files are never cleaned
  up) — plan a retention/cleanup job before long-term production use.
- `slidelab.db` is a single SQLite file; back it up on a schedule appropriate for your traffic,
  and be aware SQLite serializes writes (fine for small/medium bot traffic, a real bottleneck
  under heavy concurrent write load).
- Set `PAYMENT_ENV=PRODUCTION` only once a real Click/Payme payment-verification integration
  replaces the stub in `services/payment/providers.py` / the `TODO` in
  `bot/handlers/payment.py`'s `process_check_payment`.

## Payments: TezCheck

Customers pay on TezCheck's page with Click or Payme; the files are sent automatically.

1. TezCheck cabinet: copy the API key (`aps_…`) and the cash desk code (`cdk_…`).
2. Add a webhook endpoint `https://<your-domain>/payments/tezcheck/webhook` and copy its secret (`wbs_…`, shown once).
3. Railway → Variables: `TEZCHECK_API_KEY`, `TEZCHECK_CASH_DESK_CODE`, `TEZCHECK_WEBHOOK_SECRET`.

Every webhook is checked (HMAC-SHA256, 5-minute window) and processed once; an order is paid only
when TezCheck reports `paid` with real money (`environment: live`) for at least the order's price.
Unpaid bills are re-checked every 90 seconds, so a lost webhook never loses a sale. Without the
TezCheck variables the bot runs in DEMO mode (no real payment).

## Admin dashboard

`https://<your-domain>/admin` — revenue and statistics, orders (mark paid, resend files, cancel, CSV),
users (block, balance, message), TezCheck payments, broadcasts, settings (prices, limits, AI model,
maintenance mode, admins) and system status. Sign in with the one-time link from `/admin` in the bot,
or with `ADMIN_LOGIN` / `ADMIN_PASSWORD`.

## Database on Railway

Railway rebuilds the container on every deploy, so a SQLite file is lost. Add **PostgreSQL** to the
project and set `DATABASE_URL=${{Postgres.DATABASE_URL}}` on the bot service; tables are created and
upgraded automatically at start. Each order also keeps its deck in the database, so PDF/PPTX can be
rebuilt even after `storage/` is wiped.
