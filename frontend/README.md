# VaaniSetu — Frontend Architecture & Interfaces

This directory contains the user-facing interfaces and client applications of the **VaaniSetu (वाणीसेतु)** tactical acoustic communications suite.

---

## Directory Structure

```
frontend/
├── web/                           # Tactical Web Walkie-Talkie Interfaces
│   ├── pages/                     # Clean HTML Page Templates
│   │   ├── index.html             # Unified Dual-HUD Walkie-Talkie Simulator
│   │   ├── sender.html            # Dedicated Field Transmitter Unit (TX)
│   │   └── receiver.html          # Dedicated Command Listening Station (RX)
│   └── static/                    # High-Performance Static Web Assets
│       ├── style.css              # Military / Tactical Dark Theme Stylesheet
│       ├── app.js                 # Frontend Audio & Web-Transceiver Logic
│       ├── css/style.css          # Dual-path fallback CSS
│       └── js/app.js              # Dual-path fallback JS
└── README.md                      # This documentation
```

*(Native Android clients reside in `android/` with dedicated `:app-sender` and `:app-receiver` launcher modules leveraging the shared `:vaanisetu-core` library).*

---

## Web Interfaces

The web frontend is served directly by the unified asynchronous backend server (`backend/server/server.py`):

| Route | Interface Name | Role & Purpose |
|---|---|---|
| `/` | **Unified Dual-Phone Simulator** | Side-by-side sender and receiver simulation on a single screen with interactive PTT, volume VU meter, channel selection, and tactical macro dispatch. |
| `/sender` | **Field Transmitter Unit (TX)** | Fullscreen, dedicated field operator unit. Supports push-to-talk (Mac hardware mic or browser mic), 16 tactical macro rapid broadcasts, and live signal telemetry. |
| `/receiver` | **Command Listening Station (RX)** | Dedicated monitoring station with low-latency Server-Sent Events (SSE) ingress push (<5ms), live audio waveform visualizer, audio stream auto-playback, and emergency siren alerting. |
| `/static/*` | **Static Assets** | Optimized stylesheet and client logic with responsive design for desktop and mobile browsers. |

---

## Design System & Aesthetics

- **Tactical Dark Palette**: Engineered for low-light tactical environments using neutral slate/charcoal backgrounds (`#0d1117`, `#161b22`), border accents (`#30363d`), and active green status indicators (`#238636`, `#2ea043`).
- **Clean Tactical Badges**: Crisp military-spec text labels (e.g., `[CRITICAL]`, `[HIGH]`, `[MEDEVAC]`, `[FIRE RESCUE]`) with zero decorative AI-generated emojis.
- **Dynamic VU Level Metering**: Real-time microphone audio input feedback displaying hardware input peak and browser mic RMS levels.
- **Zero-Latency Ingress Push**: Utilizes Server-Sent Events (`EventSource('/api/events')`) with automatic fallback to polling (`/api/poll_ingress`).
