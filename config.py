from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from dotenv import load_dotenv, find_dotenv

# Force load .env file so that values in .env override any existing OS environment variables
load_dotenv(find_dotenv(), override=True)

class Settings(BaseSettings):
    BOT_TOKEN: str = "7548392011:AAExampleTokenForSlideLabBotString"
    ADMIN_IDS: str = "123456789"
    DATABASE_URL: str = "sqlite+aiosqlite:///slidelab.db"
    PAYMENT_ENV: str = "DEMO"  # "DEMO" (MockPaymentProvider) or "PRODUCTION" (Click/Payme)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5.6-sol"
    OPENAI_VISION_MODEL: str = "gpt-5.6-sol"
    # Slides and plans are written with a low-latency model thinking briefly (several times faster).
    # Leave OPENAI_FAST_MODEL empty to use OPENAI_MODEL; OPENAI_REASONING_EFFORT: none/minimal/low/medium/default.
    OPENAI_FAST_MODEL: str = "gpt-5.6-luna"
    OPENAI_REASONING_EFFORT: str = "low"
    AI_PARALLEL_REQUESTS: int = 10      # slides written at the same time
    DEFAULT_PRICE_PER_SLIDE: int = 350
    MIN_SLIDES_PER_ORDER: int = 5
    MAX_SLIDES_PER_ORDER: int = 30
    DEFAULT_LANGUAGE: str = "uz"

    # Slide images (services/deck/images.py). Providers without a key are skipped; when none
    # finds a picture, the theme's generated art is used instead.
    IMAGE_PROVIDERS: str = "pexels,pixabay,unsplash,openverse,wikimedia,openai"
    PEXELS_API_KEY: str = ""          # https://www.pexels.com/api/ (free)
    PIXABAY_API_KEY: str = ""         # https://pixabay.com/api/docs/ (free, key shown after sign-in)
    UNSPLASH_ACCESS_KEY: str = ""     # https://unsplash.com/developers (free)
    OPENVERSE_ENABLED: bool = True    # no key needed; openly licensed real photos (Openverse)
    LOCAL_PHOTO_DIR: str = ""         # development only: take photos from this folder
    WIKIMEDIA_ENABLED: bool = True    # no key needed; good for science/history pictures
    AI_IMAGES_ENABLED: bool = False   # OpenAI image generation (paid per image)
    OPENAI_IMAGE_MODEL: str = "gpt-image-1"
    OPENAI_IMAGE_QUALITY: str = "medium"

    # Click Shop API (https://docs.click.uz) -- required only for PAYMENT_ENV=PRODUCTION
    CLICK_SERVICE_ID: str = ""
    CLICK_MERCHANT_ID: str = ""
    CLICK_SECRET_KEY: str = ""

    # Payme Merchant API (https://developer.help.paycom.uz) -- required only for PAYMENT_ENV=PRODUCTION
    PAYME_MERCHANT_ID: str = ""
    PAYME_SECRET_KEY: str = ""

    # Local bind address for the payment webhook HTTP server (bot/webhook_app.py).
    # Put a reverse proxy (nginx + TLS) in front of this in production -- Click and
    # Payme both require HTTPS callback URLs.
    WEBHOOK_HOST: str = "0.0.0.0"
    WEBHOOK_PORT: int = 8080

    # Public HTTPS address of the template gallery Mini App (served by the same server at /webapp/,
    # e.g. https://your-domain.uz/webapp/). Empty = gallery is browsed with inline buttons only.
    WEBAPP_URL: str = ""

    # Flood protection (bot/middlewares/throttling.py): every user may send THROTTLE_BURST messages or
    # button presses at once, then THROTTLE_RATE per second; flooders are ignored for THROTTLE_BAN_SECONDS.
    THROTTLE_RATE: float = 1.0
    THROTTLE_BURST: int = 12
    THROTTLE_BAN_SECONDS: int = 300
    # Expensive work: presentations built at the same time (others wait in a queue) and unpaid
    # previews one user may create per day (each one costs AI requests). Admins are not limited.
    MAX_PARALLEL_BUILDS: int = 2
    MAX_PREVIEWS_PER_DAY: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def admin_id_list(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit()]

settings = Settings()

# Hosting platforms (Railway, Render, Heroku...) give the public port in $PORT and the bot must
# listen on it; Railway also exposes the public domain, which gives the Mini App address for free.
import os as _os  # noqa: E402
if _os.getenv("PORT", "").isdigit():
    settings.WEBHOOK_PORT = int(_os.environ["PORT"])
if not settings.WEBAPP_URL:
    _domain = _os.getenv("RAILWAY_PUBLIC_DOMAIN") or _os.getenv("RENDER_EXTERNAL_HOSTNAME") or ""
    if _domain:
        settings.WEBAPP_URL = f"https://{_domain.strip('/')}/webapp/"



























