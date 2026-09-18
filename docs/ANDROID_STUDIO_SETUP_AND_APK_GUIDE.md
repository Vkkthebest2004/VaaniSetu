# 📱 VaaniSetu Android Studio & APK Build Guide

Complete step-by-step instructions to import the project into **Android Studio**, sync dependencies, compile the C++ NDK native layer, and generate an installable **APK**.

---

## 📋 Prerequisites

Before opening the project, ensure you have:
1. **Android Studio** (Hedgehog, Iguana, Jellyfish, or newer).
2. **Android SDK** installed:
   - **Compile SDK**: API 34 (Android 14)
   - **Minimum SDK**: API 24 (Android 7.0)
3. **Android NDK & CMake** (installed via Android Studio SDK Manager):
   - **NDK**: Version `26.1.10909125` (or any NDK r26+)
   - **CMake**: Version `3.22.1`
4. **JDK 17** (Bundled automatically with Android Studio).

---

## 🛠️ Step 1: Open the Project in Android Studio

> [!IMPORTANT]
> Do **NOT** open the root `VaaniSetu/` directory in Android Studio. Open the **`android/`** subfolder.

1. Launch **Android Studio**.
2. On the Welcome screen, click **Open** (or go to `File` > `Open...`).
3. Browse to the project path:
   ```
   /Users/vaibhavkrishnakesarwani/Desktop/VaaniSetu/android
   ```
4. Select the **`android`** folder and click **Open**.
5. Wait for Android Studio to initialize.

---

## ⚙️ Step 2: Verify SDK, NDK & CMake

1. In Android Studio, open **Settings / Preferences**:
   - **macOS**: `Android Studio` > `Settings...` (or `Cmd + ,`)
   - **Windows/Linux**: `File` > `Settings...`
2. Navigate to: **Appearance & Behavior** > **System Settings** > **Android SDK**.
3. Click the **SDK Tools** tab:
   - Check **NDK (Side by side)**.
   - Check **CMake** (ensure `3.22.1` is checked).
   - Check **Android SDK Command-line Tools**.
4. Click **Apply** and let it download if not already installed.
5. Click **OK**.

---

## 🔄 Step 3: Sync Project with Gradle Files

1. Android Studio will automatically start a **Gradle Sync**.
2. If it does not start automatically, click the **Sync Project with Gradle Files** icon (the elephant with a blue arrow in the top-right toolbar) or go to:
   ```
   File > Sync Project with Gradle Files
   ```
3. Watch the **Build** window at the bottom. You should see:
   ```
   BUILD SUCCESSFUL
   ```
4. In the **Project** tool window on the left, switch the view dropdown to **Android**. You will see two modules:
   - **`app`**: The Material 3 walkie-talkie user interface (`WalkieTalkieActivity`, UI layouts, 3D PTT button).
   - **`vaanisetu-core`**: The Kotlin transceiver core with C++ NDK native JNI bindings.

---

## 📦 Step 4: Generate the APK (Debug & Release)

### Method A: Using the Android Studio Menu (Visual)
1. Go to the top menu bar:
   ```
   Build > Build Bundle(s) / APK(s) > Build APK(s)
   ```
2. Android Studio will compile the Kotlin source code, invoke CMake/Ninja to build `libvaanisetu_jni.so` for `arm64-v8a` and `armeabi-v7a`, and package the APK.
3. Once completed, a popup notification will appear at the bottom right:
   ```
   APK(s) generated successfully for 1 module.
   [locate]
   ```
4. Click **locate** to reveal the `.apk` file in Finder / File Explorer.

---

### Method B: Using the Built-in Terminal (One Command)
Inside Android Studio, click the **Terminal** tab at the bottom and run:
```bash
./gradlew assembleDebug
```
To build an unsigned Release APK:
```bash
./gradlew assembleRelease
```

---

## 📂 Step 5: Where to Find the Generated APK

The compiled APK is located at:
```
/Users/vaibhavkrishnakesarwani/Desktop/VaaniSetu/android/app/build/outputs/apk/debug/app-debug.apk
```

**File Size**: ~8.1 MB  
**Included Architectures**: `arm64-v8a`, `armeabi-v7a`  
**Included Shared Libraries**: `libvaanisetu_jni.so`, `libc++_shared.so`

---

## 📲 Step 6: Install & Run on Phone or Emulator

### Option 1: Run Directly from Android Studio
1. Connect an Android phone via USB (with **USB Debugging** enabled in Developer Options) **OR** start an Android Emulator.
2. In the top toolbar, select **app** in the run configuration dropdown.
3. Select your device in the target device dropdown.
4. Click the green **Run ▶** button (or press `Shift + F10`).
5. Android Studio will install the APK and launch the tactical walkie-talkie interface on the screen.

### Option 2: Install via Terminal using ADB
With your phone connected via USB:
```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

---

## 🧪 Step 7: Run Automated Unit Tests in Android Studio

To verify all transceiver algorithms and protocols:
1. In the Android Studio Project view, navigate to:
   ```
   vaanisetu-core > kotlin+java > com.vaanisetu.core (test) > CoreTransceiverUnitTest
   ```
2. Right-click `CoreTransceiverUnitTest` and select **Run 'CoreTransceiverUnitTest'**.
3. All 7 test suites will execute:
   - ✅ `testMicroRadioPacketVoicePackAndUnpack`
   - ✅ `testMicroRadioPacketMacroPackAndUnpack` (6-byte binary payload)
   - ✅ `testCorruptedCrcRejected` (CRC-16 validation)
   - ✅ `testTacticalRescorer` (Phonetic confusion & channel normalization)
   - ✅ `testAcousticProcessor` (DC baseline centering & soft tanh AGC)
   - ✅ `testEmergencySirenGenerator` (960/770Hz warble siren & +12dB prepending)
   - ✅ `testBrahmiTransliterator` (Phonetic Devanagari transliteration)
