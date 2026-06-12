"""
ryu-vision — Telegram Mini App File Explorer

Bot Telegram + HTTP server untuk akses filesystem Windows.
WebApp (Mini App) ngobrol sama bot via API HTTP.
Fitur: File Explorer, Download, Upload, System Monitor.
"""

import os
import json
import hmac
import hashlib
import stat as stat_module
import time
import logging
import platform
from pathlib import Path
from urllib.parse import unquote, quote
from datetime import datetime

import psutil

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    WebAppInfo, MenuButtonWebApp, InlineKeyboardMarkup,
    InlineKeyboardButton, FSInputFile
)
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
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(Path.home() / "Downloads" / "ryu-uploads"))

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
        if not p.exists():
            return False
        drive = p.drive
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
    if os.name == "nt":
        import subprocess
        try:
            result = subprocess.run(["wmic", "logicaldisk", "get", "name"],
                                    capture_output=True, text=True, timeout=5)
            for line in result.stdout.strip().split("\n")[1:]:
                drive = line.strip()
                if drive:
                    drives.append(drive)
        except Exception:
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
    else:
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

        try:
            content = p.read_text(encoding="utf-8", errors="strict")
            return {
                "path": str(p),
                "size": size,
                "content": content,
                "encoding": "utf-8"
            }
        except (UnicodeDecodeError, UnicodeEncodeError):
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


# ─── System Monitor ───────────────────────────────────────────────────
def get_disk_info() -> list:
    """Info penggunaan semua drive"""
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "drive": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "total_fmt": format_size(usage.total),
                "used_fmt": format_size(usage.used),
                "free_fmt": format_size(usage.free),
            })
        except PermissionError:
            disks.append({
                "drive": part.mountpoint,
                "fstype": part.fstype,
                "error": "Permission denied"
            })
    return disks


def get_cpu_info() -> dict:
    """Info CPU dan RAM"""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
            "freq_mhz": cpu_freq.current if cpu_freq else 0,
        },
        "ram": {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
            "total_fmt": format_size(mem.total),
            "used_fmt": format_size(mem.used),
            "free_fmt": format_size(mem.available),
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "percent": swap.percent,
            "total_fmt": format_size(swap.total),
            "used_fmt": format_size(swap.used),
        },
        "hostname": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "uptime_seconds": int(time.time() - psutil.boot_time()),
    }


def get_process_list(top_n: int = 15) -> list:
    """Daftar proses berjalan (sorted by CPU)"""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu": info["cpu_percent"] or 0,
                "mem": info["memory_percent"] or 0,
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort by CPU descending, take top N
    processes.sort(key=lambda p: p["cpu"], reverse=True)
    return processes[:top_n]


# ─── HTTP Server ──────────────────────────────────────────────────────
async def handle_ls(request: web.Request) -> web.Response:
    """POST /api/ls — list directory"""
    try:
        data = await request.json()
    except Exception:
        data = {}

    path = data.get("path", "C:\\")
    init_data = data.get("init_data", "")

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
    # Juga return info disk usage
    disk_info = get_disk_info()
    disk_map = {}
    for d in disk_info:
        disk_map[d["drive"]] = d

    results = []
    for d in drives:
        try:
            info = list_directory(d)
            disk = disk_map.get(d.rstrip("\\"), {})
            results.append({
                "drive": d,
                "label": d.rstrip(":\\/"),
                "items": info.get("items", []),
                "item_count": info.get("item_count", 0),
                "disk": {
                    "total_fmt": disk.get("total_fmt", "?"),
                    "used_fmt": disk.get("used_fmt", "?"),
                    "free_fmt": disk.get("free_fmt", "?"),
                    "percent": disk.get("percent", 0),
                } if disk else None,
            })
        except Exception as e:
            results.append({
                "drive": d,
                "label": d.rstrip(":\\/"),
                "error": str(e)
            })

    return web.json_response({"drives": results})


async def handle_download(request: web.Request) -> web.Response:
    """GET /api/download — download file sebagai attachment"""
    path = request.query.get("path", "")
    init_data = request.query.get("init_data", "")

    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)

    if not path or not is_path_safe(path):
        return web.json_response({"error": "Access denied"}, status=403)

    p = Path(path).resolve()
    if not p.is_file():
        return web.json_response({"error": "Not a file"}, status=404)

    try:
        return web.FileResponse(p)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


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


# ─── Favicon ──────────────────────────────────────────────────────────
async def handle_favicon(request: web.Request) -> web.Response:
    """GET /favicon.ico — serve favicon"""
    favicon_path = Path(__file__).parent.parent / "webapp" / "favicon.ico"
    if favicon_path.exists():
        return web.FileResponse(favicon_path)
    return web.Response(status=204)  # No content



async def handle_disk_api(request: web.Request) -> web.Response:
    """GET /api/disk -- daftar info drive"""
    init_data = request.query.get("init_data", "")
    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)
    return web.json_response({"disks": get_disk_info()})


async def handle_cpu_api(request: web.Request) -> web.Response:
    """GET /api/cpu -- cpu, ram, uptime"""
    init_data = request.query.get("init_data", "")
    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)
    return web.json_response(get_cpu_info())


async def handle_proc_api(request: web.Request) -> web.Response:
    """GET /api/proc -- daftar proses"""
    init_data = request.query.get("init_data", "")
    if not validate_init_data(init_data):
        return web.json_response({"error": "Unauthorized"}, status=401)
    top_n = int(request.query.get("top", "15"))
    return web.json_response({"processes": get_process_list(top_n)})


async def run_http_server():
    """Jalankan HTTP server"""
    app = web.Application()

    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            return web.Response(headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            })
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    app.middlewares.append(cors_middleware)

    # API
    app.router.add_post("/api/ls", handle_ls)
    app.router.add_post("/api/stat", handle_stat)
    app.router.add_post("/api/read", handle_read)
    app.router.add_post("/api/drives", handle_drives)
    app.router.add_get("/api/download", handle_download)
    # System Monitor API
    app.router.add_get("/api/disk", handle_disk_api)
    app.router.add_get("/api/cpu", handle_cpu_api)
    app.router.add_get("/api/proc", handle_proc_api)

    # Web
    app.router.add_get("/health", handle_health)
    app.router.add_get("/webapp", handle_webapp)
    app.router.add_get("/webapp/{filename}", handle_webapp_static)
    app.router.add_get("/favicon.ico", handle_favicon)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, API_HOST, API_PORT)
    await site.start()
    logger.info(f"HTTP server running on http://{API_HOST}:{API_PORT}")
    print(f"  🌐 API:       http://{API_HOST}:{API_PORT}")
    print(f"  🖥️  WebApp:  {WEBAPP_URL}")
    print(f"  💾 Upload:    {UPLOAD_DIR}")


# ─── Bot Handlers ─────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Welcome + tombol buka File Explorer"""
    is_https = WEBAPP_URL.startswith("https://")

    buttons = []
    if is_https:
        buttons.append([InlineKeyboardButton(
            text="📁 Buka File Explorer",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )])

    buttons.append([InlineKeyboardButton(text="💻 /cpu — CPU & RAM", callback_data="info_cpu")])
    buttons.append([InlineKeyboardButton(text="💾 /disk — Storage", callback_data="info_disk")])

    builder = InlineKeyboardMarkup(inline_keyboard=buttons)

    msg = (
        "👁️ **ryu-vision v2 — Remote File Explorer & Monitor**\n\n"
        "Jelajahi file Windows, download, upload, monitor PC langsung dari Telegram!\n\n"
        "**📁 File Explorer** — browse folder, lihat file info\n"
        "**💾 System Monitor** — /disk, /cpu, /proc\n"
        "**📥 Download** — klik file di Mini App\n"
        "**📤 Upload** — kirim file ke bot"
    )

    await message.answer(msg, reply_markup=builder)


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "**📁 ryu-vision v2 — Perintah Tersedia**\n\n"
        "**🔍 File Explorer**\n"
        "/start — Buka Mini App File Explorer\n\n"
        "**🖥️ System Monitor**\n"
        "/disk — Info penggunaan semua drive\n"
        "/cpu — CPU, RAM, dan uptime\n"
        "/proc — Daftar proses (top 15 by CPU)\n\n"
        "**📥 Download**\n"
        "Buka Mini App → klik file → bot kirim file ke chat ini\n\n"
        "**📤 Upload**\n"
        "Kirim file ke bot → auto-simpan ke `Downloads/ryu-uploads/`\n\n"
        "**🔧 Lainnya**\n"
        "/status — Cek status server & koneksi\n"
        "/help — Bantuan ini"
    )


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    drives = get_drives()
    disk_info = get_disk_info()
    disk_lines = []
    for d in disk_info:
        if "error" in d:
            disk_lines.append(f"  {d['drive']}: ❌ {d['error']}")
        else:
            bar = "█" * int(d["percent"] / 10) + "░" * (10 - int(d["percent"] / 10))
            disk_lines.append(f"  {d['drive']}: {d['used_fmt']}/{d['total_fmt']} ({d['percent']}%)")
            disk_lines.append(f"             {bar}")

    status_text = (
        "**🟢 ryu-vision v2 — Status**\n\n"
        f"**Platform:** {platform.system()} {platform.release()}\n"
        f"**Hostname:** {platform.node()}\n"
        f"**Drives:** {', '.join(drives)}\n"
        f"**Upload:** `{UPLOAD_DIR}`\n"
        f"**API:** {API_BASE_URL}\n"
        f"**WebApp:** {WEBAPP_URL}\n\n"
        "**💾 Disk Usage:**\n"
        + "\n".join(disk_lines)
    )
    await message.answer(status_text)


@dp.message(Command("disk"))
async def cmd_disk(message: types.Message):
    """Info penggunaan drive"""
    disk_info = get_disk_info()
    lines = ["**💾 Disk Usage**\n"]
    for d in disk_info:
        if "error" in d:
            lines.append(f"❌ **{d['drive']}**: {d['error']}")
        else:
            bar_len = 14
            filled = int(d["percent"] / (100 / bar_len))
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(
                f"**{d['drive']}** ({d['fstype']})\n"
                f"  {bar}  `{d['percent']:.0f}%`\n"
                f"  Total: {d['total_fmt']}\n"
                f"  Used:  {d['used_fmt']}\n"
                f"  Free:  {d['free_fmt']}\n"
            )

    await message.answer("\n".join(lines))


@dp.message(Command("cpu"))
async def cmd_cpu(message: types.Message):
    """Info CPU, RAM, uptime"""
    info = get_cpu_info()
    cpu = info["cpu"]
    ram = info["ram"]
    swap = info["swap"]

    # CPU bar
    cpu_bar_len = 14
    cpu_filled = int(cpu["percent"] / (100 / cpu_bar_len))
    cpu_bar = "█" * cpu_filled + "░" * (cpu_bar_len - cpu_filled)

    # RAM bar
    ram_filled = int(ram["percent"] / (100 / cpu_bar_len))
    ram_bar = "█" * ram_filled + "░" * (cpu_bar_len - ram_filled)

    # Uptime formatting
    uptime = info.get("uptime_seconds", 0)
    days, rem = divmod(uptime, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"

    msg = (
        "**🖥️ System Monitor**\n"
        f"Host: `{info['hostname']}`\n"
        f"OS: {info['os']}\n"
        f"Uptime: {uptime_str}\n\n"
        f"**CPU** ({cpu['count']} cores, {cpu['freq_mhz']:.0f} MHz)\n"
        f"  {cpu_bar}  `{cpu['percent']:.1f}%`\n\n"
        f"**RAM**\n"
        f"  {ram_bar}  `{ram['percent']:.1f}%`\n"
        f"  Used: {ram['used_fmt']} / {ram['total_fmt']}\n"
        f"  Free: {ram['free_fmt']}\n"
    )

    if swap["total"] > 0:
        swap_bar = "█" * int(swap["percent"] / (100 / cpu_bar_len)) + "░" * (cpu_bar_len - int(swap["percent"] / (100 / cpu_bar_len)))
        msg += (
            f"\n**Swap**\n"
            f"  {swap_bar}  `{swap['percent']:.1f}%`\n"
            f"  Used: {swap['used_fmt']} / {swap['total_fmt']}\n"
        )

    await message.answer(msg)


@dp.message(Command("proc"))
async def cmd_proc(message: types.Message):
    """Daftar proses berjalan"""
    processes = get_process_list(15)
    if not processes:
        await message.answer("❌ Tidak bisa mendapatkan daftar proses.")
        return

    lines = ["**⚙️ Top Processes (by CPU)**\n"]
    for i, p in enumerate(processes, 1):
        cpu_display = f"{p['cpu']:.1f}%" if p['cpu'] else "0%"
        mem_display = f"{p['mem']:.1f}%" if p['mem'] else "0%"
        lines.append(f"`{p['pid']:>6}` {cpu_display:>6} / {mem_display:>6} — {p['name'][:40]}")

    # Split if too long (Telegram 4096 limit)
    msg = "\n".join(lines)
    if len(msg) > 4000:
        # Send as file
        with open(Path.home() / "ryu-processes.txt", "w") as f:
            f.write(msg.replace("**", "").replace("`", ""))
        await message.answer_document(
            FSInputFile(Path.home() / "ryu-processes.txt"),
            caption="📋 Daftar proses (top 15 by CPU)"
        )
        os.unlink(Path.home() / "ryu-processes.txt")
    else:
        await message.answer(msg)


# ─── WebApp Data Handler (Download dari Mini App) ─────────────────────
@dp.message(F.web_app_data)
async def webapp_data_handler(message: types.Message):
    """Terima data dari WebApp (download request)"""
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action", "")
        path = data.get("path", "")

        logger.info(f"WebApp data: action={action}, path={path}")

        if action == "download":
            if not path or not is_path_safe(path):
                await message.answer("❌ Akses ditolak: path tidak valid.")
                return

            p = Path(path).resolve()
            if not p.is_file():
                await message.answer("❌ File tidak ditemukan.")
                return

            size = p.stat().st_size
            # Telegram bot file size limit: 50MB
            if size > 50 * 1024 * 1024:
                await message.answer(f"⚠️ File terlalu besar untuk dikirim via Telegram ({format_size(size)}). Maks 50 MB.")
                return

            try:
                await message.answer_document(
                    FSInputFile(str(p)),
                    caption=f"📥 **{p.name}**\nSize: {format_size(size)}"
                )
            except Exception as e:
                await message.answer(f"❌ Gagal mengirim file: {e}")

        else:
            await message.answer(f"⚠️ Perintah tidak dikenal: {action}")

    except json.JSONDecodeError:
        await message.answer("❌ Data WebApp tidak valid.")
    except Exception as e:
        logger.error(f"WebApp data handler error: {e}")
        await message.answer(f"❌ Error: {e}")


# ─── Upload Handler ───────────────────────────────────────────────────
@dp.message(F.document)
async def handle_upload(message: types.Message):
    """Terima file dari user — simpan ke UPLOAD_DIR"""
    doc = message.document
    file_name = doc.file_name or f"file_{doc.file_id}"
    file_size = doc.file_size or 0

    # Status
    status_msg = await message.answer(f"📤 **Mengupload...** `{file_name}` ({format_size(file_size)})")

    try:
        # Pastikan folder upload ada
        upload_path = Path(UPLOAD_DIR)
        upload_path.mkdir(parents=True, exist_ok=True)

        # Download file dari Telegram
        file_info = await bot.get_file(doc.file_id)
        dest = upload_path / file_name

        # Hindari overwrite
        counter = 1
        while dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            dest = upload_path / f"{stem} ({counter}){suffix}"
            counter += 1

        await bot.download_file(file_info.file_path, destination=str(dest))

        real_size = dest.stat().st_size
        await status_msg.edit_text(
            f"✅ **File tersimpan!**\n\n"
            f"Nama: `{file_name}`\n"
            f"Size: {format_size(real_size)}\n"
            f"Lokasi: `{dest}`\n"
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ **Upload gagal:** {e}")


# ─── Echo / Fallback ──────────────────────────────────────────────────
@dp.message()
async def cmd_echo(message: types.Message):
    """Respon ke pesan teks biasa"""
    text = message.text or "[non-text]"
    await message.answer(
        f"👋 **Halo!**\n\n"
        f"Pesan kamu: _{text}_\n\n"
        f"**Perintah tersedia:**\n"
        f"• /start — Buka File Explorer\n"
        f"• /disk — Info drive\n"
        f"• /cpu — CPU & RAM\n"
        f"• /proc — Daftar proses\n"
        f"• /help — Semua perintah\n"
        f"• /status — Status server\n\n"
        f"📤 Atau kirim file untuk upload ke PC!"
    )


# ─── Main Entry ───────────────────────────────────────────────────────
async def main():
    logger.info("Bot starting...")

    # Buat folder upload
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Jalankan HTTP server dulu
    await run_http_server()

    # Set menu button
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
    print(f"\n  ✅ ryu-vision v2 siap!")
    print(f"  🤖 Bot @RyuVisionBot")
    print(f"  🌐 API: http://{API_HOST}:{API_PORT}")
    print(f"  🖥️  WebApp: {WEBAPP_URL}")
    print(f"  💾 Upload:  {UPLOAD_DIR}")
    print()

    # Jalankan polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
