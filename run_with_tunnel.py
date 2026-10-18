"""
Starts the bot together with a free Cloudflare quick tunnel, so the template gallery Mini App works
on a home computer without a domain.

    python run_with_tunnel.py

1. runs `cloudflared tunnel --url http://localhost:<WEBHOOK_PORT>`
2. waits for the https://....trycloudflare.com address it prints
3. starts the bot with WEBAPP_URL=<that address>/webapp/ (the .env file is not changed)
4. stops the tunnel when the bot stops (Ctrl+C)

The quick-tunnel address changes on every start; that is fine because it is passed to the bot each
time. Send "🎨 Presentation yaratish" again after a restart so Telegram gets buttons with the new
address. For a permanent address use a server with your own domain and set WEBAPP_URL in .env.
"""
import asyncio
import os
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def find_cloudflared() -> str:
    exe = shutil.which("cloudflared")
    if exe:
        return exe
    for p in (r"C:\Program Files (x86)\cloudflared\cloudflared.exe", r"C:\Program Files\cloudflared\cloudflared.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\cloudflared.exe"),
              "/usr/local/bin/cloudflared", "/opt/homebrew/bin/cloudflared", "/usr/bin/cloudflared"):
        if os.path.exists(p):
            return p
    sys.exit("❌ cloudflared topilmadi. O‘rnating: winget install --id Cloudflare.cloudflared (keyin yangi PowerShell oching)")


def start_tunnel(port: int):
    proc = subprocess.Popen([find_cloudflared(), "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    found = {}

    def reader():
        for line in proc.stdout:
            m = URL_RE.search(line)
            if m and "url" not in found:
                found["url"] = m.group(0)
            if "ERR" in line and "url" not in found:
                print("  cloudflared:", line.strip())

    threading.Thread(target=reader, daemon=True).start()
    t0 = time.time()
    while "url" not in found:
        if proc.poll() is not None:
            sys.exit("❌ cloudflared to‘xtab qoldi (internetni tekshiring).")
        if time.time() - t0 > 60:
            proc.terminate()
            sys.exit("❌ 60 soniyada tunnel manzili olinmadi. Qayta urinib ko‘ring.")
        time.sleep(0.3)
    return proc, found["url"]


def main():
    sys.path.insert(0, ROOT)
    from config import settings  # noqa: E402  (reads .env for the port)

    port = int(settings.WEBHOOK_PORT or 8080)
    print("⏳ Cloudflare tunnel ochilmoqda...")
    proc, url = start_tunnel(port)
    webapp = url + "/webapp/"
    os.environ["WEBAPP_URL"] = webapp
    settings.WEBAPP_URL = webapp
    print(f"✅ Mini App manzili: {webapp}")
    print("   (Telegram'da \"🎨 Presentation yaratish\" ni qayta bosing — tugmalar yangi manzil bilan keladi)")
    print("   DNS tarqalishi uchun 10-30 soniya kerak bo‘lishi mumkin.\n")
    try:
        import main as bot_main  # noqa: E402
        asyncio.run(bot_main.main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        proc.terminate()
        print("Tunnel yopildi.")


if __name__ == "__main__":
    main()
