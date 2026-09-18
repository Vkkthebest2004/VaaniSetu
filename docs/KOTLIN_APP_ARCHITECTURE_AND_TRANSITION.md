# VaaniSetu Android (Kotlin) — Modular Architecture & Transition Blueprint

> **System**: VaaniSetu / iTantra Offline Walkie-Talkie  
> **Target OS**: Android 7.0+ (API Level 24 to 34)  
> **Architectural Paradigm**: Multi-Module Clean Architecture • MVI/MVVM • Kotlin Coroutines/Flow • Native C++ NDK Bridge

---

## 1. Executive Summary & Transition Goals

The transition from the initial Python mathematical prototyping engine to a production-grade Android Kotlin application is designed to achieve:
1. **Zero-Latency Push-to-Talk (PTT)**: Deterministic audio capture and playback with < 20 ms buffer latency.
2. **Sub-200MB Mobile Footprint**: Efficient packaging of INT8 quantized models without bloated APK sizes.
3. **Decoupled Multi-Module Architecture**: Clean separation between audio DSP, neural inference, radio protocols, mesh networking, and UI.
4. **Resilient Offline Networking**: Autonomous mesh routing across WiFi Direct, Bluetooth RFCOMM/BLE, and ad-hoc UDP broadcast without requiring internet connectivity or Google Play Services.

---

## 2. Multi-Module Project Structure

The Android project is structured into modular Gradle subprojects to enforce strict dependency boundaries, enable parallel builds, and facilitate targeted unit testing:

```
android/
├── build.gradle.kts                   # Root build configuration
├── settings.gradle.kts                # Multi-project module inclusion
│
├── core/
│   ├── protocol/                      # :core:protocol
│   │   ├── build.gradle.kts           # Pure Kotlin / JVM module (no Android dependencies)
│   │   └── src/main/kotlin/com/vaanisetu/core/protocol/
│   │       ├── MicroRadioProtocol.kt  # 3-byte bit-packed header, MicroRadioPacket
│   │       ├── IndicScriptCompressor.kt # 1-byte offset Indic script compression
│   │       ├── TacticalMacro.kt       # 10 emergency distress macros & localized phrases
│   │       └── CRC16.kt               # CRC-16-CCITT packet checksum
│   │
│   ├── audio/                         # :core:audio
│   │   ├── build.gradle.kts           # Android Library (AudioRecord, Oboe C++ bindings)
│   │   └── src/main/kotlin/com/vaanisetu/core/audio/
│   │       ├── AudioRecorder.kt       # 16kHz 16-bit PCM mic capture with circular buffer
│   │       ├── AudioPlayer.kt         # Low-latency AudioTrack / Oboe speaker sink
│   │       └── AcousticProcessor.kt   # Soft tanh AGC limiter & DC baseline filter
│   │
│   ├── native/                        # :core:native
│   │   ├── build.gradle.kts           # NDK CMake external build integration
│   │   └── src/main/
│   │       ├── cpp/CMakeLists.txt     # Compiles libvaanisetu_jni.so for arm64-v8a/armeabi-v7a
│   │       └── kotlin/com/vaanisetu/core/native/
│   │           ├── NativeSTT.kt       # JNI wrapper for Sherpa-ONNX Zipformer / Whisper
│   │           ├── NativeTTS.kt       # JNI wrapper for Piper VITS neural synthesizer
│   │           └── NativeVAD.kt       # JNI wrapper for Silero VAD state machine
│   │
│   └── mesh/                          # :core:mesh
│       ├── build.gradle.kts           # Networking & wireless sockets
│       └── src/main/kotlin/com/vaanisetu/core/mesh/
│           ├── MeshRouter.kt          # UDP broadcast over channels 1-16 (port 8989)
│           ├── P2PTransport.kt        # Direct TCP sockets for unicast streaming (port 8988)
│           └── BluetoothMesh.kt       # RFCOMM serial sockets / BLE advertising
│
├── feature/
│   ├── walkietalkie/                  # :feature:walkietalkie
│   │   ├── build.gradle.kts           # Jetpack Compose UI & ViewModel
│   │   └── src/main/kotlin/com/vaanisetu/feature/walkietalkie/
│   │       ├── WalkieTalkieViewModel.kt # PTT state machine, channel knob, audio visualizer
│   │       ├── WalkieTalkieScreen.kt    # Tactical dark-mode HUD with live VU meter
│   │       └── PttTouchHandler.kt       # Hardware volume key & touch PTT bindings
│   │
│   └── emergency/                     # :feature:emergency
│       ├── build.gradle.kts           # Alert override and siren generator
│       └── src/main/kotlin/com/vaanisetu/feature/emergency/
│           ├── EmergencyAlertManager.kt # Hardware volume override, dual-tone siren
│           └── TacticalMacroGrid.kt     # One-touch quick distress macro triggers
│
└── app/                               # :app
    ├── build.gradle.kts               # Application packaging & Manifest
    └── src/main/
        ├── AndroidManifest.xml        # Audio, WiFi, and WakeLock permissions
        └── kotlin/com/vaanisetu/app/
            ├── VaaniSetuApp.kt        # Application class & model path initialization
            ├── WalkieTalkieActivity.kt# Main launcher activity
            └── WalkieTalkieService.kt # Foreground Service for background PTT listening
```

---

## 3. Step-by-Step Transition Strategy (Python $\to$ C++ $\to$ Kotlin)

```
┌─────────────────────────┐       ┌─────────────────────────┐       ┌─────────────────────────┐
│     PHASE 1: PROTOTYPE  │  ──►  │    PHASE 2: NATIVE CORE │  ──►  │   PHASE 3: KOTLIN APP   │
│  - Python DSP & PyTorch │       │  - C++17 Engine Core    │       │  - Android Studio SDK   │
│  - Bit-packing & tests  │       │  - Sherpa-ONNX / Piper  │       │  - Jetpack Compose UI   │
│  - Web Walkie-Talkie    │       │  - JNI Shared Library   │       │  - UDP Broadcast Mesh   │
└─────────────────────────┘       └─────────────────────────┘       └─────────────────────────┘
```

### Step 1: Protocol Porting (Completed)
* Ported `protocol.py` directly to `MicroRadioProtocol.kt`.
* **Zero Discrepancy**: Bit fields, magic nibble (`0xA`), Indic base offsets, and CRC-16 polynomial (`0x1021`) match exactly.
* Ensures an Android device running Kotlin can communicate with a laptop running Python or a tactical hardware unit running C++.

### Step 2: Native C++ Integration via JNI
* C++ engine (`cpp/src/stt_engine.cpp`, `cpp/src/tts_engine.cpp`) is wrapped by `cpp/jni/vaanisetu_jni.cpp`.
* Gradle invokes CMake via `externalNativeBuild`:
  ```kotlin
  externalNativeBuild {
      cmake {
          path = file("../../cpp/CMakeLists.txt")
          version = "3.22.1"
      }
  }
  ```
* Generates optimized shared libraries:
  * `libvaanisetu_jni.so` for `arm64-v8a` (modern 64-bit phones)
  * `libvaanisetu_jni.so` for `armeabi-v7a` (older low-end devices with 1–2 GB RAM)

### Step 3: Zero-Copy Audio Pipeline
* Audio samples captured by Android's `AudioRecord` are stored in direct native-allocated buffers (`ByteBuffer.allocateDirect()`).
* JNI methods receive raw pointers via `GetDirectBufferAddress()` or `GetPrimitiveArrayCritical()`.
* **Benefit**: Eliminates JVM garbage collection pauses during real-time speech recognition.

### Step 4: Background Operation with Foreground Service
* PTT walkie-talkies must receive incoming broadcasts even when the phone screen is turned off or in a pocket.
* Implement `WalkieTalkieService.kt` with a persistent notification and `PARTIAL_WAKE_LOCK`.
* CPU remains at minimal frequency (< 1%) listening on the UDP socket without triggering Android OS battery throttling (Doze Mode exemption).

---

## 4. Hardware Audio Focus & Emergency Preemption

```
Incoming Packet ──► Check PacketType == EMERGENCY_ALERT or Macro != NONE
                 ├─► FALSE: Standard audio playback at user volume
                 └─► TRUE:  Emergency Preemption Routine
                             ├─► 1. Request AudioFocus with STREAM_ALARM
                             ├─► 2. Set AudioManager.STREAM_ALARM to MAX_VOLUME
                             ├─► 3. Trigger 2-pulse haptic vibration motor
                             ├─► 4. Play dual-tone siren (960Hz / 770Hz warble)
                             └─► 5. Synthesize localized distress message
```

* Implemented in `EmergencyAlertManager.kt`.
* Bypasses "Do Not Disturb" and silent mode to guarantee life-saving messages are heard in emergency scenarios.

---

## 5. Model Asset Packaging & Storage Strategy

Neural model weights must be available offline on the device filesystem for ONNX Runtime / Sherpa-ONNX.

### Asset Distribution Architecture
1. **Base Installation**:
   * Models are bundled in the Android `assets/models/` folder:
     * `models/stt/encoder.int8.onnx` (~45 MB)
     * `models/stt/decoder.onnx` (~4 MB)
     * `models/stt/joiner.int8.onnx` (~6 MB)
     * `models/stt/tokens.txt`
     * `models/tts/en_US-lessac-low.onnx` (~64 MB)
     * `models/vad/silero_vad.onnx` (~0.6 MB)
2. **First-Launch Extraction**:
   * On initial boot, `VaaniSetuApp` unpacks assets from the APK into internal storage (`context.getExternalFilesDir(null)` or `context.filesDir`).
   * Avoids re-extraction on subsequent launches by checking MD5 hashes or version timestamps.
3. **Optional Dynamic Delivery**:
   * For ultra-low entry download size (< 30 MB APK), additional Indian regional voice models can be fetched as on-demand Play Feature Delivery modules when WiFi is initially available.

---

## 6. Verification and Testing Framework

| Level | Component | Test Target | Tooling |
|:---|:---|:---|:---|
| **Unit Test** | `:core:protocol` | Bit-packing roundtrip, Indic decompression, CRC16 | JUnit 4 / Roborlectric |
| **Unit Test** | `:core:mesh` | UDP packet broadcast, port reuse, channel filtering | Mockito / CoroutineTest |
| **Instrumentation** | `:core:native` | JNI memory leaks, STT initialization, TTS synthesis | AndroidX Test Runner |
| **System Test** | Hardware PTT | Mic capture $\to$ STT $\to$ Micro-packet $\to$ TTS $\to$ Speaker | Dual Physical Test Devices |
