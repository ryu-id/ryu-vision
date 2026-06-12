# ryu-vision 👁️📁

**Telegram Mini App — Remote File Explorer & System Monitor untuk Windows**

Jelajahi filesystem Windows, download file, upload file, dan monitor PC langsung dari Telegram!

## 🚀 Cara Kerja

```
Telegram App ←→ Bot Telegram ←→ HTTP API Server ←→ Windows Filesystem
     │
     └── WebApp (Mini App) — UI file explorer + info drive
```

1. **Bot Telegram** (aiogram 3.x) — perintah `/start`, `/disk`, `/cpu`, `/proc`, upload/download file
2. **HTTP API** (aiohttp) — REST endpoints untuk filesystem + system monitor
3. **WebApp (HTML/JS/CSS)** — UI file explorer dengan Telegram theme
4. **Filesystem Windows** — baca direktori, file info, konten file
5. **Ngrok Tunnel** — ekspos server lokal ke HTTPS untuk Mini App Telegram

## ✨ Fitur

| Fitur | Description |
|---|---|
| 📂 **File Explorer** | Navigasi folder Windows via Mini App |
| 💾 **Multi-drive** | Deteksi otomatis semua drive (C:, D:, dll) + info disk usage |
| 📄 **Info file** | Ukuran, tanggal, tipe file |
| 📥 **Download** | Klik file di Mini App → bot kirim file ke chat (max 50MB) |
| 📤 **Upload** | Kirim file ke bot → auto-simpan ke `Downloads/ryu-uploads/` |
| 🖥️ **System Monitor** | `/disk` (storage), `/cpu` (CPU/RAM), `/proc` (proses) |
| 🔒 **Aman** | Read-only, path traversal protection, drive whitelist, HMAC validation |
| 🎨 **Telegram theme** | Otomatis pake tema gelap/terang Telegram |

## 📁 Struktur

```
ryu-vision/
├── README.md
├── .gitignore
├── bot/
│   ├── main.py              # Bot Telegram + HTTP API server (aiogram + aiohttp)
│   ├── requirements.txt     # aiogram, aiohttp, python-dotenv, psutil
│   └── .env.example         # Template konfigurasi
└── webapp/
    ├── index.html           # Halaman utama Mini App
    ├── style.css            # Styling (Telegram theme)
    └── app.js               # Logic file explorer + API client
```

## 🛠️ Instalasi

```bash
# Clone
git clone https://github.com/ryu-id/ryu-vision.git
cd ryu-vision

# Setup Python env
cd bot
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt

# Konfigurasi
cp .env.example .env
# Isi BOT_TOKEN dan API_BASE_URL di .env
```

## ⚙️ Konfigurasi (.env)

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Token bot Telegram dari @BotFather |
| `API_HOST` | `0.0.0.0` | IP bind HTTP server |
| `API_PORT` | `8765` | Port HTTP server |
| `API_BASE_URL` | `http://localhost:8765` | URL publik bot API (ganti ke URL ngrok) |
| `WEBAPP_URL` | `{API_BASE_URL}/webapp` | URL Mini App |
| `ALLOWED_DRIVES` | `C:,D:,E:,F:` | Drive yang bisa diakses |
| `UPLOAD_DIR` | `~/Downloads/ryu-uploads` | Folder penyimpanan upload |

## 🚦 Menjalankan

### 1. Start server

```bash
cd bot
.venv\Scripts\activate
python main.py
```

Server akan:
- 🟢 Start HTTP API di `http://0.0.0.0:8765`
- 🤖 Mulai polling bot Telegram
- 🔗 Set menu button WebApp (jika URL HTTPS)
- 💾 Buat folder upload `Downloads/ryu-uploads/`

### 2. Tunnel (ngrok) — untuk akses dari Telegram

```bash
# Install ngrok dan daftar di https://ngrok.com
ngrok config add-authtoken <token_dashboard>
ngrok http 8765
```

Copy URL ngrok (misal `https://xxx.ngrok-free.dev`) → update `.env`:
```
API_BASE_URL=https://xxx.ngrok-free.dev
WEBAPP_URL=https://xxx.ngrok-free.dev/webapp
```

Restart bot. Menu button akan otomatis aktif karena URL sudah HTTPS.

### 3. Buka di Telegram

➡️ Buka bot → **/start** → klik **"📁 Buka File Explorer"**

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Buka Mini App File Explorer + shortcut buttons |
| `/disk` | 💾 Info penggunaan semua drive (bar chart) |
| `/cpu` | 🖥️ CPU usage, RAM, Swap, uptime |
| `/proc` | ⚙️ Daftar top 15 proses by CPU |
| `/status` | Status server, drives, disk usage |
| `/help` | Semua perintah |

## 📥 Download File (dari Mini App)

1. Buka Mini App via **/start**
2. Navigasi ke folder yang diinginkan
3. Klik **file** (bukan folder)
4. Bot akan mengirim file tersebut ke chat Telegram

⚠️ Maks 50 MB (batas Telegram Bot API).

## 📤 Upload File (ke PC)

1. Kirim file langsung ke @RyuVisionBot
2. Bot akan menyimpan ke folder: `C:\Users\<user>\Downloads\ryu-uploads\`
3. Nama file di-dedup (jika sudah ada, ditambahkan `(2)`)

## 🔌 API Endpoints

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/ls` | List directory | ✅ init_data |
| `POST` | `/api/stat` | File/dir info | ✅ init_data |
| `POST` | `/api/read` | Baca file teks | ✅ init_data |
| `POST` | `/api/drives` | Daftar drive + isi + disk usage | ✅ init_data |
| `GET` | `/api/download?path=...` | Download file sebagai attachment | ✅ query init_data |
| `GET` | `/api/disk` | Info storage semua drive | ✅ query init_data |
| `GET` | `/api/cpu` | CPU, RAM, uptime | ✅ query init_data |
| `GET` | `/api/proc?top=15` | Daftar proses by CPU | ✅ query init_data |
| `GET` | `/health` | Health check | ❌ |
| `GET` | `/webapp` | Serve Mini App HTML | ❌ |
| `GET` | `/webapp/{filename}` | Serve static file (js/css) | ❌ |
| `GET` | `/favicon.ico` | Serve favicon | ❌ |

### Auth via `init_data`

Semua endpoint `/api/*` memerlukan `init_data` di body JSON (POST) atau query string (GET):
```json
{
  "init_data": "query_id=...&user=...&auth_date=...&hash=..."
}
```

**Dev mode:** kirim `"init_data": "dev_mode=1"` untuk testing lokal (tanpa validasi hash).

### Contoh request

```bash
# Daftar drive (dengan dev mode)
curl -s -X POST http://localhost:8765/api/drives \
  -H "Content-Type: application/json" \
  -d '{"init_data":"dev_mode=1"}' | python3 -m json.tool

# List direktori
curl -s -X POST http://localhost:8765/api/ls \
  -H "Content-Type: application/json" \
  -d '{"init_data":"dev_mode=1", "path":"C:\\Users"}' | python3 -m json.tool

# Info CPU
curl -s "http://localhost:8765/api/cpu?init_data=dev_mode=1" | python3 -m json.tool

# Download file
curl -s -o file.zip "http://localhost:8765/api/download?init_data=dev_mode=1&path=C:\\path\\to\\file.zip"
```

## 🔧 Known Fixes & Tips

### Static files 404 (CSS/JS)

HTML menggunakan path absolut di bawah `/webapp/`:
```html
<link rel="stylesheet" href="/webapp/style.css">
<script src="/webapp/app.js"></script>
```

### API URL dari HP

`app.js` menggunakan API path relatif (`''`) — otomatis menggunakan domain yang sama (ngrok/public URL). Jangan set ke `http://localhost:8765` karena localhost di HP ≠ server.

### WebApp button error "Only HTTPS links allowed"

Telegram hanya mengizinkan URL HTTPS untuk WebApp button. Solusi: gunakan ngrok tunnel, lalu set `WEBAPP_URL` ke URL ngrok.

### `charset must not be in content_type argument`

Gunakan `content_type=..., charset=...` sebagai parameter terpisah, bukan digabung di content_type string.

## 🔒 Keamanan

- ✅ Validasi HMAC Telegram WebApp init data (SHA256)
- ✅ Path traversal protection (`../` ditolak)
- ✅ Drive whitelist (hanya drive di `ALLOWED_DRIVES`)
- ✅ Read-only (tidak ada endpoint write/delete — upload via bot terbatas ke folder tertentu)
- ✅ Environment variable untuk konfigurasi rahasia
- ⚠️ Dev mode bypass (`dev_mode=1`) — hanya untuk testing lokal

## 📦 Dependencies

- Python 3.10+
- `aiogram` 3.x — Telegram Bot API
- `aiohttp` — HTTP server
- `python-dotenv` — konfigurasi .env
- `psutil` — system monitoring (CPU, RAM, disk)
- Ngrok CLI — HTTPS tunnel

## 📋 Changelog

### v2.0 — System Monitor + Download/Upload
- 📥 Download file via Mini App (main.py web_app_data handler)
- 📤 Upload file ke PC (bot document handler)
- 🖥️ `/disk` — storage info (psutil)
- 🖥️ `/cpu` — CPU, RAM, uptime
- 🖥️ `/proc` — daftar proses
- 🔌 API: `/api/disk`, `/api/cpu`, `/api/proc`, `/api/download`
- 💾 Disk usage info di `/api/drives`
- 🚀 Bot v2 dengan inline keyboard di `/start`

### v1.0 — File Explorer
- File Explorer Mini App
- Multi-drive support
- File info (size, date)
- Ngrok tunnel setup
- Dev mode bypass

---

_Dibuat oleh [ryu-id](https://github.com/ryu-id)_
