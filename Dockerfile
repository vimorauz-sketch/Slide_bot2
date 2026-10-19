# Railway / any Docker host: python + Chromium (for slide rendering) + PPTX metric fonts.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-liberation fonts-crosextra-carlito fonts-crosextra-caladea fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt && python -m playwright install --with-deps chromium

COPY . .

# Railway sets $PORT; config.py makes the web server (payments + Mini App) listen on it.
CMD ["python", "main.py"]
