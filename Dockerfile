# Railway / any Docker host: python + Chromium (for slide rendering) + PPTX metric fonts.
#
# The Debian release is pinned (bookworm): plain "python:3.12-slim" now follows the newest Debian,
# and Playwright's "install --with-deps" only knows the package names of the releases it supports.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app

# libatomic1 first: Playwright's bundled Node.js (playwright/driver/node) is linked against
# libatomic.so.1, and even "playwright install" runs through it — without the library the build stops
# with "libatomic.so.1: cannot open shared object file". The fonts give PPTX/PDF the right metrics.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libatomic1 ca-certificates \
        fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Python packages, then Chromium with its system libraries, then the code: a code change rebuilds only
# the last layer. The Chromium layer ends with a launch check, so a missing library fails the build here
# and not later while a customer's slides are being drawn.
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* \
    && printf 'from playwright.sync_api import sync_playwright\nwith sync_playwright() as p:\n    p.chromium.launch().close()\nprint("chromium ok")\n' | python -

COPY . .

# Railway sets $PORT; config.py makes the web server (payments + Mini App) listen on it.
CMD ["python", "main.py"]
