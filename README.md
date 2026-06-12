# ryu-vision 👁️📁

**Telegram Mini App — File Explorer untuk Windows**

Jelajahi filesystem Windows langsung dari Telegram!

## 🚀 Cara Kerja

```
Telegram App ←→ Bot Server ←→ Windows Filesystem
     │                              │
     └── WebApp (Mini App)          └── API baca file & direktori
```

1. **Bot Telegram** (aiogram) — menerima perintah, serve WebApp
2. **HTTP API** (aiohttp) — endpoint REST untuk akses filesystem
3. **WebApp** (HTML/JS) — UI file explorer di dalem Telegram
4. **Filesystem Windows** — baca direktori, file info, konten file

## 📁 Struktur

```
ryu-vision/
├── README.md
├── .gitignore
├── bot/
│   ├── main.py           # Bot Telegram + HTTP API server
│   ├── requirements.txt  # aiogram, aiohttp, python-dotenv
│   └── .env.example      # Template konfigurasi
└── webapp/
    ├── index.html        # Halaman utama Mini App
    ├── style.css         # Styling (Telegram theme)
    └── app.js            # Logic file explorer
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
| `API_BASE_URL` | `http://localhost:8765` | URL publik bot API |
| `WEBAPP_URL` | `{API_BASE_URL}/webapp` | URL Mini App |
| `ALLOWED_DRIVES` | `C:,D:,E:,F:` | Drive yang bisa diakses |

## 🚦 Menjalankan

```bash
cd bot
.venv\Scripts\activate
python main.py
```

Untuk akses dari luar (Telegram):
```bash
# Pakai ngrok
ngrok http 8765
# Copy URL ngrok → API_BASE_URL di .env
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ls` | List directory |
| `POST` | `/api/stat` | File/dir info |
| `POST` | `/api/read` | Baca file teks |
| `POST` | `/api/drives` | Daftar drive |
| `GET` | `/health` | Health check |
| `GET` | `/webapp` | Serve Mini App |

## 🔒 Keamanan

- Validasi HMAC Telegram WebApp init data
- Path traversal protection
- Drive whitelist
- Read-only (tidak bisa hapus/edit file)

---

_Dibuat oleh [ryu-id](https://github.com/ryu-id)_
