# ryu-vision 👁️📁

**Telegram Mini App — File Explorer untuk Windows**

Jelajahi filesystem Windows langsung dari Telegram via Mini App!

## 🚀 Cara Kerja

```
Telegram App ←→ Bot Telegram ←→ HTTP API Server ←→ Windows Filesystem
     │
     └── WebApp (Mini App) — UI file explorer di dalam Telegram
```

1. **Bot Telegram** (aiogram 3.x) — menerima perintah `/start`, serve WebApp, set menu button
2. **HTTP API** (aiohttp) — endpoint REST untuk akses filesystem
3. **WebApp (HTML/JS/CSS)** — UI file explorer dengan Telegram theme
4. **Filesystem Windows** — baca direktori, file info, konten file (read-only)
5. **Ngrok Tunnel** — ekspos server lokal ke HTTPS untuk WebApp Telegram

## ✨ Fitur

- 📂 **Browse direktori** — navigasi folder Windows dari HP
- 💾 **Multi-drive** — deteksi otomatis semua drive (C:, D:, dll)
- 📄 **Info file** — ukuran, tanggal, tipe file
- 🔒 **Aman** — read-only, path traversal protection, drive whitelist, HMAC validation
- 🎨 **Telegram theme** — otomatis pake tema gelap/terang Telegram

## 📁 Struktur

```
ryu-vision/
├── README.md
├── .gitignore
├── bot/
│   ├── main.py            # Bot Telegram + HTTP API server (aiogram + aiohttp)
│   ├── requirements.txt   # aiogram, aiohttp, python-dotenv
│   └── .env.example       # Template konfigurasi
└── webapp/
    ├── index.html         # Halaman utama Mini App
    ├── style.css          # Styling (Telegram theme)
    └── app.js             # Logic file explorer + API client
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

## 🔌 API Endpoints

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/ls` | List directory | ✅ init_data |
| `POST` | `/api/stat` | File/dir info | ✅ init_data |
| `POST` | `/api/read` | Baca file teks | ✅ init_data |
| `POST` | `/api/drives` | Daftar drive + isi | ✅ init_data |
| `GET` | `/health` | Health check | ❌ |
| `GET` | `/webapp` | Serve Mini App HTML | ❌ |
| `GET` | `/webapp/{filename}` | Serve static file (js/css) | ❌ |

### Auth via `init_data`

Semua endpoint `/api/*` memerlukan `init_data` di body JSON:
```json
{
  "init_data": "query_id=...&user=...&auth_date=...&hash=..."
}
```

Nilai `init_data` otomatis dikirim oleh Telegram WebApp via `tg.initData`.

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

## 🔒 Keamanan

- ✅ Validasi HMAC Telegram WebApp init data (SHA256)
- ✅ Path traversal protection (`../` ditolak)
- ✅ Drive whitelist (hanya drive di `ALLOWED_DRIVES`)
- ✅ Read-only (tidak ada endpoint write/delete)
- ✅ Environment variable untuk konfigurasi rahasia
- ⚠️ Dev mode bypass (`dev_mode=1`) — hanya untuk testing lokal

## 📦 Dependencies

- Python 3.10+
- `aiogram` 3.x — Telegram Bot API
- `aiohttp` — HTTP server
- `python-dotenv` — konfigurasi .env
- `pyngrok` (opsional) — tunnel ngrok via Python
- Ngrok CLI — HTTPS tunnel

---

_Dibuat oleh [ryu-id](https://github.com/ryu-id)_
