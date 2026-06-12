# ryu-vision 👁️

**Computer vision toolkit for Hermes Agent — integrasi vision, webcam, deteksi objek, dan AI vision di Windows.**

Proyek ini adalah turunan/setup dari teknologi WiFi sensing & computer vision yang dioptimalkan untuk ekosistem Hermes Agent di Windows. Terinspirasi dari [RuView](https://github.com/ruvnet/RuView) dan berbagai framework vision modern.

## ✨ Fitur Utama

- 🔍 **Object Detection** — YOLO, MediaPipe, COCO-SSD via Python
- 📷 **Webcam Integration** — real-time capture & analysis via Hermes Agent
- 📡 **WiFi Sensing (opsional)** — ESP32 CSI integration untuk deteksi kehadiran
- 🧠 **AI Vision** — integrasi dengan OpenAI Vision, Anthropic Vision
- 🪟 **Windows Optimized** — PowerShell wrapper, batch scripts, COM port management

## 📁 Struktur

```
ryu-vision/
├── README.md
├── scripts/          # PowerShell, batch, Python utilities
├── models/           # Model weights & configs
├── tools/            # Vision tools & utilities
├── docs/             # Dokumentasi
└── examples/         # Contoh penggunaan
```

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/ryu-id/ryu-vision.git
cd ryu-vision

# Setup Python env
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 📦 Dependencies

- Python 3.10+
- OpenCV
- MediaPipe
- Hermes Agent tools (opsional)

---

_Dibuat oleh [ryu-id](https://github.com/ryu-id)_
