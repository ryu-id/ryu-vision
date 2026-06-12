"""
ryu-vision — Telegram Mini App File Explorer

Bot Telegram + HTTP server untuk akses filesystem Windows.
WebApp (Mini App) ngobrol sama bot via API HTTP.
"""

import os
import json
import hmac
import hashlib
import stat as stat_module
import time
import logging
from pathlib import Path
from urllib.parse import unquote, quote
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, MenuButtonWebApp, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

import aiohttp
from aiohttp import web

# ─── Config ───────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8765"))
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8765")
WEBAPP_URL = os.getenv("WEBAPP_URL", f"{API_BASE_URL}/webapp")
ALLOWED_DRIVES = os.getenv("ALLOWED_DRIVES", "C:,D:,E:,F:").split(",")

# ─── Bot Setup ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ryu-vision")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ─── WebApp Auth ──────────────────────────────────────────────────────
BOT_TOKEN_BYTES = BOT_TOKEN.encode() if BOT_TOKEN else b""


def validate_init_data(init_data: str) -> bool:
    """Validasi Telegram WebApp init data"""
    if not init_data:
        return False
    # Dev mode: bypass validasi untuk testing
    if init_data.strip() == "dev_mode=1":
        return True
    try:
        # Parse init data
        params = {}
        for pair in init_data.split("&"):
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            params[k] = unquote(v)

        # Check hash
        received_hash = params.pop("hash", None)
        if not received_hash:
            return False

        # Build data check string
        sorted_params = sorted(params.items())
        data_check = "\n".join(f"{k}={v}" for k, v in sorted_params)

        # Compute HMAC
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN_BYTES, hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

        return computed_hash == received_hash
    except Exception as e:
        logger.warning(f"Init data validation error: {e}")
        return False


# ─── Filesystem API ───────────────────────────────────────────────────
def is_path_safe(path: str) -> bool:
    """Cegah path traversal dan batasi ke drive yang diizinkan"""
    try:
        p = Path(path).resolve()
        # Cek path traversal
        if not p.exists():
            return False
        # Cek drive
        drive = p.drive  # "C:", "D:", etc
        if drive and drive not in ALLOWED_DRIVES:
            return False
        return True
    except Exception:
        return False


def format_size(size_bytes: int) -> str:
    """Format ukuran file"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def list_directory(path: str) -> dict:
    """List isi directory, return dict untuk JSON"""
    p = Path(path).resolve()
    if not p.is_dir():
        return {"error": "Not a directory", "path": str(p)}

    items = []
    errors = []
    try:
        for entry in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                st = entry.stat()
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                    "size": st.st_size if not entry.is_dir() else 0,
                    "size_fmt": format_size(st.st_size) if not entry.is_dir() else "",
                    "modified": datetime.fromtimestamp(st.st_mtime).isoformat() if st.st_mtime else "",
                    "created": datetime.fromtimestamp(st.st_ctime).isoformat() if st.st_ctime else "",
                })
            except PermissionError:
                items.append({
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir() if entry.is_dir() else False,
                    "size": 0,
                    "size_fmt": "",
                    "modified": "",
                    "created": "",
                    "error": "Permission denied"
                })
            except OSError as e:
                errors.append(f"{entry.name}: {e}")

        # Dapatkan parent
        parent = str(p.parent) if p.parent != p else ""

        return {
            "path": str(p),
            "name": p.name,
            "parent": parent,
            "drives": [],
            "items": items,
            "item_count": len(items),
            "errors": errors,
            "total_size": sum(it["size"] for it in items if not it["is_dir"]),
        }
    except PermissionError:
        return {"error": "Permission denied", "path": str(p)}
    except Exception as e:
        return {"error": str(e), "path": str(p)}


def get_drives() -> list:
    """Dapatkan daftar drive Windows"""
    drives = []
    if os.name == "nt":  # Windows
        import subprocess
        try:
            result = subprocess.run(["wmic", "logicaldisk", "get", "name"],
                                    capture_output=True, text=True, timeout=5)
            for line in result.stdout.strip().split("\n")[1:]:
                drive = line.strip()
                if drive:
                    drives.append(drive)
        except Exception:
            # Fallback: cek drive A-Z
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
    else:
        # Linux/Mac — return root
        drives.append("/")
    return drives


def get_file_content(path: str, max_size: int = 1_000_000) -> dict:
    """Baca konten file (text) — maks 1MB"""
    p = Path(path).resolve()
    if not p.is_file():
        return {"error": "Not a file"}

    try:
        size = p.stat().st_size
        if size > max_size:
            return {
                "error": "File too large",
                "size": size,
                "max_size": max_size
            }

        # Deteksi apakah binary
        try:
            content = p.read_text(encoding="utf-8", errors="strict")
            return {
                "path": str(p),
                "size": size,
                "content": content,
                "encoding": "utf-8"
            }
        except (UnicodeDecodeError, UnicodeEncodeError):
            # Binary — return base64
            import base64
            with open(p, "rb") as f:
                raw = f.read()
            return {
                "path": str(p),
                "size": size,
                "content": base64.b64encode(raw).decode(),
                "encoding": "base64",
                "mime_hint": "application/octet-stream"
            }
    except PermissionError:
        return {"error": "Permission denied"}
    except Exception as e:
        return {"error": str(e)}


# ─── HTTP Server ──────────────────────────────────────────────────────
async def handle_ls(request: web.Request) -> web.Response:
    """POST /api/ls — list directory"""
    try:
        data = await request.json()
    except Exception:
        data = {}

    path = data.get("path", "C:\\")
    init_data = data.get("init_data", "")

    # Validasi
    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)

    if not is_path_safe(path):
        return web.json_response({"error": "Access denied"}, status=403)

    result = list_directory(path)
    return web.json_response(result)


async def handle_stat(request: web.Request) -> web.Response:
    """POST /api/stat — get file/dir info"""
    try:
        data = await request.json()
    except Exception:
        data = {}

    path = data.get("path", "")
    init_data = data.get("init_data", "")

    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)

    if not path or not is_path_safe(path):
        return web.json_response({"error": "Access denied"}, status=403)

    result = list_directory(path)
    return web.json_response(result)


async def handle_read(request: web.Request) -> web.Response:
    """POST /api/read — baca konten file"""
    try:
        data = await request.json()
    except Exception:
        data = {}

    path = data.get("path", "")
    init_data = data.get("init_data", "")

    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)

    if not path or not is_path_safe(path):
        return web.json_response({"error": "Access denied"}, status=403)

    result = get_file_content(path)
    return web.json_response(result)


async def handle_drives(request: web.Request) -> web.Response:
    """POST /api/drives — daftar drive"""
    try:
        data = await request.json()
    except Exception:
        data = {}

    init_data = data.get("init_data", "")

    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)

    drives = get_drives()
    results = []
    for d in drives:
        try:
            st = os.statvfs(d) if hasattr(os, 'statvfs') else None
            info = list_directory(d)
            results.append({
                "drive": d,
                "label": d.rstrip(":\\/"),
                "items": info.get("items", []),
                "item_count": info.get("item_count", 0),
            })
        except Exception as e:
            results.append({
                "drive": d,
                "label": d.rstrip(":\\/"),
                "error": str(e)
            })

    return web.json_response({"drives": results})


async def handle_health(request: web.Request) -> web.Response:
    """GET /health — health check"""
    return web.json_response({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "drives": get_drives(),
        "platform": os.name,
    })


async def handle_webapp(request: web.Request) -> web.Response:
    """GET /webapp — serve webapp frontend"""
    try:
        webapp_path = Path(__file__).parent.parent / "webapp" / "index.html"
        if webapp_path.exists():
            text = webapp_path.read_text(encoding="utf-8")
            return web.Response(text=text, content_type="text/html", charset="utf-8")
        return web.Response(text="Webapp not found", status=404)
    except Exception as e:
        logger.error(f"Webapp error: {e}")
        return web.Response(text=f"Error: {e}", status=500)


async def handle_webapp_static(request: web.Request) -> web.Response:
    """Serve file statis webapp (.js, .css)"""
    filename = request.match_info.get("filename", "")
    static_path = Path(__file__).parent.parent / "webapp" / filename
    if static_path.exists():
        ext = static_path.suffix
        ct = {
            ".js": "application/javascript",
            ".css": "text/css",
            ".html": "text/html",
            ".json": "application/json",
        }.get(ext, "application/octet-stream")
        text = static_path.read_text(encoding="utf-8")
        return web.Response(text=text, content_type=ct)
    return web.Response(text="Not found", status=404)


async def run_http_server():
    """Jalankan HTTP server"""
    app = web.Application()

    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    # OPTIONS handler
    async def handle_options(request):
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        })

    app.middlewares.append(cors_middleware)

    app.router.add_post("/api/ls", handle_ls)
    app.router.add_post("/api/stat", handle_stat)
    app.router.add_post("/api/read", handle_read)
    app.router.add_post("/api/drives", handle_drives)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/webapp", handle_webapp)
    app.router.add_get("/webapp/{filename}", handle_webapp_static)
    app.router.add_route("OPTIONS", "/api/{tail:.*}", handle_options)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, API_HOST, API_PORT)
    await site.start()
    logger.info(f"HTTP server running on http://{API_HOST}:{API_PORT}")
    print(f"  🌐 API:       http://{API_HOST}:{API_PORT}")
    print(f"  🖥️  WebApp:  {WEBAPP_URL}")


# ─── Bot Handlers ─────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Welcome + tombol buka File Explorer"""
    is_https = WEBAPP_URL.startswith("https://")
    
    if is_https:
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📁 Buka File Explorer",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )]
        ])
    else:
        builder = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔧 Setup Tunnel Dulu",
                url="https://ngrok.com/download"
            )]
        ])
    
    msg = (
        "👁️ **ryu-vision — File Explorer**\n\n"
        "Jelajahi file Windows langsung dari Telegram!"
    )
    if not is_https:
        msg += (
            "\n\n⚠️ **WebApp belum aktif**\n"
            "Mini App butuh HTTPS tunnel.\n"
            "Setelah ngrok jalan, update `WEBAPP_URL` di `.env`"
        )
    
    await message.answer(msg, reply_markup=builder)


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "**📁 ryu-vision File Explorer**\n\n"
        "**Perintah:**\n"
        "/start — Buka File Explorer\n"
        "/help — Bantuan ini\n"
        "/status — Cek status server\n\n"
        "**Fitur:**\n"
        "• Navigasi folder Windows\n"
        "• Lihat file info (size, tanggal)\n"
        "• Baca file teks\n"
        "• Tampilkan drive C:, D:, E:, dll"
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    drives = get_drives()
    status_text = (
        "**🟢 ryu-vision Status**\n\n"
        f"**Platform:** {os.name}\n"
        f"**Drives:** {', '.join(drives)}\n"
        f"**API:** {API_BASE_URL}\n"
        f"**WebApp:** {WEBAPP_URL}"
    )
    await message.answer(status_text)


@dp.message()
async def cmd_echo(message: types.Message):
    """Respon ke pesan teks biasa"""
    text = message.text or "[non-text]"
    await message.answer(
        f"👋 **Halo!**\n\n"
        f"Pesan kamu: _{text}_\n\n"
        f"Gunakan perintah:\n"
        f"• /start — Buka File Explorer\n"
        f"• /help — Bantuan\n"
        f"• /status — Cek server"
    )


# ─── Main Entry ───────────────────────────────────────────────────────
async def main():
    logger.info("Bot starting...")

    # Jalankan HTTP server dulu
    await run_http_server()

    # Set menu button (gagal diam-diam kalau URL masih HTTP)
    try:
        if WEBAPP_URL.startswith("https://"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📁 File Explorer",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            )
            logger.info("Menu button set")
        else:
            logger.warning(f"WebApp URL bukan HTTPS ({WEBAPP_URL}), skip menu button")
            print(f"  ⚠️  Skipping menu button — WEBAPP_URL harus HTTPS")
            print(f"  💡 Set API_BASE_URL ke URL publik (ngrok) di .env")
    except Exception as e:
        logger.warning(f"Menu button gagal: {e}")

    logger.info("Bot started — polling...")
    print(f"\n  ✅ ryu-vision bot siap!")
    print(f"  🤖 Bot: @CodeActBot")
    print(f"  🌐 API: http://{API_HOST}:{API_PORT}")
    print(f"  🖥️  WebApp: {WEBAPP_URL}")
    print(f"  💬 Mulai chat: https://t.me/CodeActBot")
    print()

    # Jalankan polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
