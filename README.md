# VaaniSetu (वाणी सेतु) — Offline Tactical Voice Transceiver & Walkie-Talkie

[![Android](https://img.shields.io/badge/Android-API%2024%2B-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://developer.android.com)
[![Kotlin](https://img.shields.io/badge/Kotlin-1.9-7F52FF?style=for-the-badge&logo=kotlin&logoColor=white)](https://kotlinlang.org)
[![C++](https://img.shields.io/badge/C%2B%2B-17%20%2F%20NDK-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)](https://isocpp.org)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/Pytest-59%2F59%20Passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![Offline](https://img.shields.io/badge/Offline-100%25%20Air--Gapped-orange?style=for-the-badge&logo=shield&logoColor=white)](#)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue?style=for-the-badge)](LICENSE)

**VaaniSetu (वाणी सेतु)** is an ultra-lightweight, 100% offline tactical voice transceiver and digital walkie-talkie platform engineered for mission-critical disaster recovery, defense field operations, and air-gapped environments.

By fusing on-device neural Speech-to-Text (STT), neural Text-to-Speech (TTS), and an ultra-compressed **6-byte binary MicroRadio protocol** (achieving **99.96% bandwidth savings**), VaaniSetu enables real-time multilingual voice broadcasts across **10 Indic languages** on standard Android smartphones, embedded micro-radios, and web simulators with **zero internet, cell tower, or cloud dependency**.

---

## 📱 Separate Sender & Receiver Applications (Live Android Apps)

VaaniSetu provides **two dedicated standalone Android applications** that install and run side-by-side on the same device or across separate phones:

| VaaniSetu Sender (`com.vaanisetu.sender`) | VaaniSetu Receiver (`com.vaanisetu.receiver`) |
| :---: | :---: |
| <img src="docs/screenshots/sender_app_transceiver.png" width="280" alt="VaaniSetu Sender App" /> | <img src="docs/screenshots/receiver_app_station.png" width="280" alt="VaaniSetu Receiver App" /> |
| **Field Transceiver Unit**: 3D PTT Button, offline STT, 6-byte binary broadcast, tactical emergency macros | **Command Listening Station**: Acoustic spectrum monitor, packet decode, auto-neural Indic TTS readout |

### 🔒 Complete Features & Neural Models Separation Matrix

To optimize memory, CPU, and APK footprints for field deployment, all features, permissions, and neural models are **strictly isolated**:

| Dimension | VaaniSetu Sender (`com.vaanisetu.sender`) | VaaniSetu Receiver (`com.vaanisetu.receiver`) |
| :--- | :--- | :--- |
| **Role & Purpose** | Field Voice Transceiver & Emergency Transmitter | Command Listening Station & Indic Voice Synthesizer |
| **Android Permissions** | `RECORD_AUDIO`, `INTERNET`, `ACCESS_WIFI_STATE`, `VIBRATE` | `INTERNET`, `ACCESS_WIFI_STATE`, `VIBRATE`, `FOREGROUND_SERVICE`<br>*(Strictly zero `RECORD_AUDIO` permission)* |
| **Dedicated Neural Models** | • **Speech-to-Text (STT)**: Whisper Tiny / Zipformer Small (`models/stt/`)<br>• **Voice Activity Detection**: Silero VAD ONNX (`models/vad/`)<br>• **Domain Adapters**: Indic military vocabulary (`models/indic_adapter/`) | • **Text-to-Speech (TTS)**: Piper VITS Hindi Rohan / English Lessac (`models/tts/`)<br>• **Phoneme Database**: eSpeak-NG Indic dictionary (`espeak-ng-data/`)<br>• **Tokens**: Character & phoneme mapping (`tokens.txt`) |
| **Omitted Models** | **Strictly ZERO TTS models**: No Piper VITS, no neural vocoders, no eSpeak data | **Strictly ZERO STT models**: No Whisper/Zipformer weights, no VAD weights |
| **Runtime Pipeline** | `SenderPipeline` & `SenderModelManager` (Mic → VAD → STT → Rescorer → Packet Pack → Mesh TX) | `ReceiverPipeline` & `ReceiverModelManager` (Mesh RX → Packet Unpack → CRC → Neural TTS → Speaker) |
| **Local Audio Feedback** | Sidetone / Mic Loopback (replays actual recorded mic PCM) & tactical roger beeps | Dual-tone warble emergency siren (800-1200Hz) & Indic neural voice playback |
| **CLI Runner** | `python scripts/run_sender.py --channel 8` (TTS excluded from RAM) | `python scripts/run_receiver.py --channel 8` (STT & Mic excluded from RAM) |
| **Model Sync (ADB)** | `./scripts/sync_app_models.sh sender` | `./scripts/sync_app_models.sh receiver` |

### Additional Interactive Features

| Startup Radar Animation | Slide-Up Tactical Macros | Emergency Override Broadcast |
| :---: | :---: | :---: |
| <img src="docs/screenshots/splash_boot_animation.png" width="240" alt="Startup Animation" /> | <img src="docs/screenshots/tactical_macros_drawer.png" width="240" alt="Tactical Macros" /> | <img src="docs/screenshots/emergency_broadcast_active.png" width="240" alt="Emergency Override" /> |

---

## ⚡ Performance Benchmarks (Real-Time Factor / Speed)

| Module | Implementation | Model | Model Size | Speed (Latency) | Real-Time Factor (RTF) |
|:---|:---|:---|:---:|:---:|:---:|
| **STT** | **Native C++** | Zipformer-small (int8) | ~107 MB | **61 ms** (for 6.6s audio) | **0.009 RTF (~110x faster)** |
| **STT** | Python wrapper | Zipformer-small (int8) | ~107 MB | **80 ms** (for 6.6s audio) | **0.012 RTF (~80x faster)** |
| **TTS** | **Native C++** | Piper VITS (lessac-low) | ~64 MB | **132 ms** (for 2.4s audio) | **0.054 RTF (~18x faster)** |
| **TTS** | Python wrapper | Piper VITS (lessac-low) | ~64 MB | **60 ms** (for 1.4s audio) | **0.040 RTF (~25x faster)** |
| **VAD** | Native C++ / Python | Silero VAD (ONNX) | ~0.6 MB | **< 1 ms** per window | **< 0.005 RTF** |

---

## 🚀 Dual Architecture: C++, Kotlin & Python

VaaniSetu provides a 3-tier architecture so every layer can be used:

```
┌─────────────────────────────────────────────────────────────┐
│                    KOTLIN (Android Layer)                   │
│  - NativeSTT.kt (ASR Controller)                            │
│  - NativeTTS.kt (TTS Controller)                            │
│  - AudioRecorder.kt (16kHz mono low-latency mic input)      │
│  - AudioPlayer.kt (16kHz mono low-latency speaker playback) │
│  - P2PTransport.kt (WiFi Direct / Bluetooth P2P sockets)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ JNI (0-copy memory bridge)
┌──────────────────────────────▼──────────────────────────────┐
│                    C++ NATIVE ENGINE CORE                   │
│  - vaanisetu::STTEngine (Zipformer INT8 + Silero VAD)       │
│  - vaanisetu::TTSEngine (Piper VITS ONNX)                   │
│  - vaanisetu::WavIO (Zero-dependency PCM WAV I/O)           │
│  - Standalone binaries: vaanisetu_stt_cli, vaanisetu_tts_cli│
└─────────────────────────────────────────────────────────────┘
                               ▲
┌──────────────────────────────┴──────────────────────────────┐
│                    PYTHON (Prototyping & Tests)             │
│  - SherpaSTTEngine & SherpaTTSEngine                        │
│  - Automated pytest test suite                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Clean Repository Structure

```
VaaniSetu/
├── android/                       # Native Android Application & Library
│   ├── app/                       # Material 3 Walkie-Talkie Android App
│   │   └── src/main/
│   │       ├── AndroidManifest.xml
│   │       ├── kotlin/com/vaanisetu/app/   # WalkieTalkieActivity, Service, EmergencyAlert
│   │       └── res/                        # 3D PTT selectors, LCD themes, tactical icons
│   ├── vaanisetu-core/            # Kotlin Transceiver Library Module
│   │   ├── build.gradle.kts       # Configured with CMake & Android NDK (arm64-v8a, armeabi-v7a)
│   │   └── src/
│   │       ├── main/kotlin/com/vaanisetu/core/  # TransceiverEngine, MicroRadio, DSP, JNI
│   │       └── test/kotlin/com/vaanisetu/core/  # Core transceiver unit tests (100% pass)
│   ├── build.gradle.kts           # Root gradle config
│   ├── settings.gradle.kts        # Multi-module settings
│   └── gradlew                    # Gradle 8.9 wrapper
├── frontend/                      # User-Facing Client Interfaces
│   ├── web/                       # Tactical Web Walkie-Talkie Interfaces
│   │   ├── pages/                 # Clean HTML Templates (index.html, sender.html, receiver.html)
│   │   └── static/                # Static assets (style.css, app.js)
│   └── README.md                  # Frontend Architecture & Route Guide
│
├── backend/                       # Backend Transceiver & Processing Services
│   ├── server/                    # Asynchronous AioHTTP Tactical Server (server.py)
│   └── README.md                  # Backend Architecture & Service Guide
│
├── web_walkie_talkie/             # Backward-Compatibility Shim (delegates to backend/server)
│
├── cpp/                           # High-Performance Native C++ Core Engine
│   ├── CMakeLists.txt             # Dual cross-platform build (macOS / Linux / Android NDK)
│   ├── include/vaanisetu/         # C++ headers (stt_engine.hpp, tts_engine.hpp, wav_io.hpp)
│   ├── src/                       # STT & TTS engine implementations + CLI executables
│   └── jni/                       # JNI shared library bridge (`libvaanisetu_jni`)
│
├── vaanisetu/                     # Python Transceiver Core
│   ├── transceiver/               # MicroRadio binary protocol & WiFi mesh router
│   ├── stt/                       # Acoustic front-end, Silero VAD, Tactical Rescorer
│   ├── tts/                       # Piper VITS Indic synthesis & dual-engine router
│   └── utils/                     # Model downloader helpers
│
├── inference/                     # AI Pipeline Subsystems
│   ├── iasr/                      # Streaming ASR engine
│   ├── ilangid/                   # Fast Indic language identification classifier
│   ├── itranslate/                # Offline neural translation engine
│   ├── ibrain/                    # Conversation router & concise reasoning engine
│   └── ivoice/                    # Streaming clause-splitting TTS
│
├── ai/                            # Unified AI Package (Re-exports inference engines)
│
├── audio/                         # Audio DSP & Testing Infrastructure
│   ├── preprocessing/             # Whisper-safe AGC, DC removal, Telephone codec filter
│   ├── vad/                       # Silero VAD real-time state machine
│   └── samples/                   # Reference audio fixtures (cpp_output, hindi_test, tts_output)
│
├── runtime/                       # Production Runtime Servers & State Machines
│   ├── server.py                  # AioHTTP API server
│   ├── conversation/              # Conversation state machine with barge-in preemption
│   └── memory/                    # Model lifecycle and active memory management
│
├── datasets/                      # Datasets & Stress Test Manifests
│   ├── evaluation/                # Multilingual stress-test audio files and manifests
│   └── manifest_builder.py        # Dataset manifest generation tool
│
├── benchmarks/                    # Military & Extreme Environment Benchmarks
│   └── military_stress_test.py    # 0dB SNR rotorcraft, artillery blast, and RF jamming tests
│
├── evaluation/                    # Automated Benchmark Reports & Metric Calculators
│   ├── benchmark_report.json      # Comprehensive metrics (WER, CER, Latency)
│   └── benchmark_report.md        # Formatted benchmark documentation
│
├── models/                        # Offline Neural ONNX Models (Int8 Quantized)
│   ├── stt/                       # Zipformer-small int8 ASR
│   ├── tts/                       # Piper VITS TTS & eSpeak-NG data
│   ├── vad/                       # Silero VAD ONNX
│   └── indic_adapter/             # Trained Indic neural adapters
│
├── scripts/                       # Developer & Automation Utilities
│   ├── download_models.py         # Automated model downloader
│   ├── train_indic_model.py       # Metal/CUDA/CPU neural adapter training & quantization
│   ├── test_stt.py                # CLI speech recognition tester
│   └── test_tts.py                # CLI voice synthesis tester
│
├── tests/                         # Pytest Automated Test Suites (59/59 passing, 100% pass)
│
├── docs/                          # Comprehensive Architectural Documentation
│   ├── TEN_SLIDE_TECH_PLAN.md                     # Executive 10-slide architecture plan
│   ├── KOTLIN_APP_ARCHITECTURE_AND_TRANSITION.md   # Android migration & transition blueprint
│   ├── VAANISETU_DEEP_STUDY_GUIDE.md               # End-to-end technical deep-dive study guide
│   └── PROJECT_WALKTHROUGH.md                     # Full development & verification walkthrough
│
├── pyproject.toml                 # Standard Python project packaging & pytest configuration
├── requirements.txt               # Main project Python dependencies
└── .gitignore                     # Git configuration ignoring large model binaries & builds
```

---

## 🛠️ Multi-Platform Run Guides

### 1. Android Applications (Separate Sender & Receiver)
The Android project builds two standalone applications sharing the `:vaanisetu-core` library:
```bash
cd android

# Build both standalone APKs (Sender & Receiver)
./gradlew assembleDebug

# Or build specifically either app:
./gradlew :app-sender:assembleDebug      # Output: app-sender/build/outputs/apk/debug/app-sender-debug.apk
./gradlew :app-receiver:assembleDebug    # Output: app-receiver/build/outputs/apk/debug/app-receiver-debug.apk

# Run unit tests across all modules
./gradlew test

# Install both applications side-by-side to a connected phone or emulator:
adb install -r app-sender/build/outputs/apk/debug/app-sender-debug.apk
adb install -r app-receiver/build/outputs/apk/debug/app-receiver-debug.apk
```

### 2. Standalone Terminal CLI Runners (Pure Sender & Pure Receiver)
You can test the isolated field transmitter and command listening station directly from separate terminal windows without running the web server or Android studio:

```bash
# Terminal 1 — Pure Command Listening Station (Receiver CLI)
# Listens on UDP:8989, decodes MicroRadio frames, and speaks via Indic Neural TTS
python scripts/run_receiver.py --channel 8

# Terminal 2 — Pure Field Transmitter Unit (Sender CLI)
# Captures Mac microphone audio, transcribes with offline STT, and broadcasts binary packets
python scripts/run_sender.py --channel 8
```

### 3. Selective Model Management & Device Synchronization
Download and push only the exact neural weights required for each specific device role:

```bash
# 1. Selectively download models
python scripts/download_models.py --target sender    # Downloads only STT (Zipformer) + VAD (Silero)
python scripts/download_models.py --target receiver  # Downloads only Indic Neural TTS (Piper VITS)
python scripts/download_models.py --target all       # Downloads all models

# 2. Synchronize models to connected Android devices via ADB
./scripts/sync_app_models.sh sender    # Pushes STT/VAD to /sdcard/.../com.vaanisetu.sender/
./scripts/sync_app_models.sh receiver  # Pushes TTS to /sdcard/.../com.vaanisetu.receiver/
```

### 4. Tactical Web Walkie-Talkie Simulator
The web application provides dedicated Field Transmitter and Command Listening interfaces alongside a unified dual simulator:
```bash
# Start the canonical backend server
python backend/server/server.py

# Or via backward-compatible entrypoint
python web_walkie_talkie/server.py

# Open your browser:
# -> Unified Simulator: http://localhost:8080/
# -> Field Transmitter (TX): http://localhost:8080/sender
# -> Command Receiver (RX): http://localhost:8080/receiver
```

### 5. Standalone Native C++ Core
For maximum performance without Python or Android dependencies:
```bash
cd cpp
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
cmake --build .

# Run native STT CLI
./vaanisetu_stt_cli ../../audio/samples/hindi_test.wav

# Run native TTS CLI
./vaanisetu_tts_cli "Emergency medical team dispatched" output.wav
```

### 6. Python Testing & Verification
```bash
# Activate virtual environment
source .venv/bin/activate

# Run automated test suites
pytest tests/
```

