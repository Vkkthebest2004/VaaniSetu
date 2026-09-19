#!/usr/bin/env bash
# ==============================================================================
# VaaniSetu — Dedicated Model Sync Script for Android
#
# Pushes only the specific neural models needed by each standalone application:
#   • Sender:   models/stt/ + models/vad/ (TTS excluded)
#   • Receiver: models/tts/ (STT/VAD excluded)
#
# Usage:
#   ./scripts/sync_app_models.sh sender    # Push STT/VAD to com.vaanisetu.sender
#   ./scripts/sync_app_models.sh receiver  # Push TTS to com.vaanisetu.receiver
#   ./scripts/sync_app_models.sh all       # Push to both applications
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"

echo "============================================================"
echo "  VaaniSetu — Mobile Neural Model Sync (ADB)"
echo "  Target: ${TARGET^^}"
echo "============================================================"

# Check for ADB
if ! command -v adb &> /dev/null; then
    echo "❌ ADB not found in PATH. Please ensure Android SDK platform-tools are installed."
    exit 1
fi

DEVICE_COUNT=$(adb devices | grep -v "List" | grep "device$" | wc -l | tr -d ' ')
if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo "⚠️  No connected Android device or emulator detected via ADB."
    echo "   Ensure your phone or emulator is running and authorized with 'adb devices'."
    exit 1
fi

sync_sender_models() {
    echo ""
    echo "📤 Syncing SENDER Models (com.vaanisetu.sender)..."
    local SENDER_BASE="/sdcard/Android/data/com.vaanisetu.sender/files/models"
    adb shell "mkdir -p ${SENDER_BASE}/stt ${SENDER_BASE}/vad ${SENDER_BASE}/indic_adapter"

    # Push STT models
    if [ -d "${PROJECT_ROOT}/models/stt" ]; then
        echo "   • Pushing STT weights to ${SENDER_BASE}/stt/..."
        adb push "${PROJECT_ROOT}/models/stt/"* "${SENDER_BASE}/stt/" 2>/dev/null || true
    fi

    # Push VAD models
    if [ -d "${PROJECT_ROOT}/models/vad" ]; then
        echo "   • Pushing VAD weights to ${SENDER_BASE}/vad/..."
        adb push "${PROJECT_ROOT}/models/vad/"* "${SENDER_BASE}/vad/" 2>/dev/null || true
    fi

    # Push Indic Adapter
    if [ -d "${PROJECT_ROOT}/models/indic_adapter" ]; then
        echo "   • Pushing Indic Adapters to ${SENDER_BASE}/indic_adapter/..."
        adb push "${PROJECT_ROOT}/models/indic_adapter/"* "${SENDER_BASE}/indic_adapter/" 2>/dev/null || true
    fi

    echo "✅ Sender models synced. (TTS models strictly excluded)"
}

sync_receiver_models() {
    echo ""
    echo "📤 Syncing RECEIVER Models (com.vaanisetu.receiver)..."
    local RECEIVER_BASE="/sdcard/Android/data/com.vaanisetu.receiver/files/models"
    adb shell "mkdir -p ${RECEIVER_BASE}/tts"

    # Push TTS models
    if [ -d "${PROJECT_ROOT}/models/tts" ]; then
        echo "   • Pushing Neural TTS weights to ${RECEIVER_BASE}/tts/..."
        adb push "${PROJECT_ROOT}/models/tts/"* "${RECEIVER_BASE}/tts/" 2>/dev/null || true
    fi

    echo "✅ Receiver models synced. (STT & VAD models strictly excluded)"
}

case "$TARGET" in
    sender)
        sync_sender_models
        ;;
    receiver)
        sync_receiver_models
        ;;
    all)
        sync_sender_models
        sync_receiver_models
        ;;
    *)
        echo "Usage: $0 [sender|receiver|all]"
        exit 1
        ;;
esac

echo ""
echo "🎉 Model sync operation complete."
