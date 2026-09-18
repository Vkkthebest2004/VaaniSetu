package com.vaanisetu.core

import java.io.Closeable

/**
 * Native Voice Activity Detection (VAD) wrapper for Android.
 *
 * Uses the ultra-lightweight Silero VAD ONNX model (~16 KB active memory)
 * to detect speech presence in 32ms audio windows.
 *
 * Implements a 4-state machine:
 *   SILENCE → POSSIBLE_SPEECH → ACTIVE_SPEECH → HANGOVER → SILENCE
 *
 * During SILENCE and POSSIBLE_SPEECH states, no heavy STT inference runs,
 * achieving < 1% idle CPU utilization on mobile devices.
 */
class NativeVAD : Closeable {

    enum class SpeechState {
        SILENCE,
        POSSIBLE_SPEECH,
        ACTIVE_SPEECH,
        HANGOVER
    }

    private var nativeHandle: Long = 0
    private var _state: SpeechState = SpeechState.SILENCE
    private var hangoverFrames: Int = 0

    val isInitialized: Boolean get() = nativeHandle != 0L
    val state: SpeechState get() = _state
    val isSpeechActive: Boolean get() = _state == SpeechState.ACTIVE_SPEECH || _state == SpeechState.HANGOVER

    // Thresholds for the 4-state machine
    private var speechThreshold = 0.65f
    private var silenceThreshold = 0.35f
    private var hangoverMaxFrames = 10  // ~300ms at 30ms per frame

    /**
     * Initialize the native VAD engine with the Silero ONNX model.
     */
    fun init(modelPath: String, threshold: Float = 0.65f): Boolean {
        speechThreshold = threshold
        silenceThreshold = threshold * 0.54f  // ~0.35 for default 0.65

        nativeHandle = nativeInit(modelPath)
        return nativeHandle != 0L
    }

    /**
     * Process a single audio frame (typically 32ms = 512 samples at 16kHz)
     * and update the speech state machine.
     *
     * @param samples Float32 PCM audio samples for one frame.
     * @return Current speech state after processing.
     */
    fun processFrame(samples: FloatArray): SpeechState {
        if (!isInitialized) return SpeechState.SILENCE

        val probability = nativeProcess(nativeHandle, samples)
        updateStateMachine(probability)
        return _state
    }

    private fun updateStateMachine(probability: Float) {
        when (_state) {
            SpeechState.SILENCE -> {
                if (probability > speechThreshold) {
                    _state = SpeechState.POSSIBLE_SPEECH
                }
            }
            SpeechState.POSSIBLE_SPEECH -> {
                if (probability > speechThreshold) {
                    _state = SpeechState.ACTIVE_SPEECH
                } else {
                    _state = SpeechState.SILENCE
                }
            }
            SpeechState.ACTIVE_SPEECH -> {
                if (probability < silenceThreshold) {
                    _state = SpeechState.HANGOVER
                    hangoverFrames = 0
                }
            }
            SpeechState.HANGOVER -> {
                hangoverFrames++
                if (probability > speechThreshold) {
                    _state = SpeechState.ACTIVE_SPEECH
                    hangoverFrames = 0
                } else if (hangoverFrames >= hangoverMaxFrames) {
                    _state = SpeechState.SILENCE
                    hangoverFrames = 0
                }
            }
        }
    }

    /** Reset the state machine back to SILENCE. */
    fun reset() {
        _state = SpeechState.SILENCE
        hangoverFrames = 0
        if (isInitialized) nativeReset(nativeHandle)
    }

    override fun close() {
        if (nativeHandle != 0L) {
            nativeRelease(nativeHandle)
            nativeHandle = 0L
        }
        _state = SpeechState.SILENCE
    }

    protected fun finalize() { close() }

    // --- Native JNI declarations ---
    private external fun nativeInit(modelPath: String): Long
    private external fun nativeProcess(handle: Long, samples: FloatArray): Float
    private external fun nativeReset(handle: Long)
    private external fun nativeRelease(handle: Long)

    companion object {
        init {
            try {
                System.loadLibrary("vaanisetu_jni")
            } catch (e: UnsatisfiedLinkError) {
                // Loaded dynamically when bundled in APK
            }
        }
    }
}
