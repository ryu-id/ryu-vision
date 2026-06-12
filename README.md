# ryu-vision 👁️

**Telegram Mini App — integrasi vision & AI dalam Telegram.**

Proyek ini adalah **Telegram Mini App** (WebApp) yang menggabungkan:
- 🤖 **Bot Telegram** — handler commands & interaksi
- 🌐 **Mini App Web** — UI interaktif di dalam Telegram
- 👁️ **Vision tools** — integrasi kamera, upload gambar, AI vision

## 📁 Struktur

```
ryu-vision/
├── README.md
├── .gitignore
├── bot/                # Kode bot Telegram (Python)
│   ├── main.py
│   └── requirements.txt
├── webapp/             # Mini App frontend (HTML/JS)
│   ├── index.html
│   ├── app.js
│   └── style.css
└── tools/              # Utility tools
```

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/ryu-id/ryu-vision.git
cd ryu-vision

# Setup bot
cd bot
python -m venv .venv
source .venv/bin/activate  # atau .venv\Scripts\activate (Windows)
pip install -r requirements.txt
```

## 🔧 Tech Stack

- **Python** (aiogram / python-telegram-bot)
- **Telegram WebApp API** (JS)
- **Hermes Agent** (integrasi tools)

---

_Dibuat oleh [ryu-id](https://github.com/ryu-id)_
