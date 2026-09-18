package com.vaanisetu.core

import java.io.Closeable

/**
 * Native Speech-to-Text Engine wrapper for Android.
 *
 * Interfaces directly with the C++ sherpa-onnx core via JNI
 * for zero-overhead, ultra-fast speech recognition on low-end ARM devices.
 */
class NativeSTT : Closeable {

    private var nativeHandle: Long = 0

    val isInitialized: Boolean
        get() = nativeHandle != 0L

    /**
     * Initialize the native STT engine with model paths.
     */
    fun init(
        encoderPath: String,
        decoderPath: String,
        joinerPath: String,
        tokensPath: String,
        vadModelPath: String = "",
        threads: Int = 2
    ): Boolean {
        if (isInitialized) {
            close()
        }
        nativeHandle = nativeInit(
            encoder = encoderPath,
            decoder = decoderPath,
            joiner = joinerPath,
            tokens = tokensPath,
            vadModel = vadModelPath,
            threads = threads
        )
        return nativeHandle != 0L
    }

    /**
     * Transcribe float32 PCM audio samples [-1.0f, 1.0f].
     */
    fun transcribe(samples: FloatArray): String {
        check(isInitialized) { "NativeSTT engine is not initialized" }
        return nativeTranscribe(nativeHandle, samples)
    }

    /**
     * Transcribe a WAV file from the filesystem.
     */
    fun transcribeFile(wavPath: String, useVad: Boolean = false): String {
        check(isInitialized) { "NativeSTT engine is not initialized" }
        return nativeTranscribeFile(nativeHandle, wavPath, useVad)
    }

    override fun close() {
        if (nativeHandle != 0L) {
            nativeRelease(nativeHandle)
            nativeHandle = 0L
        }
    }

    protected fun finalize() {
        close()
    }

    // --- Native JNI declarations ---
    private external fun nativeInit(
        encoder: String,
        decoder: String,
        joiner: String,
        tokens: String,
        vadModel: String,
        threads: Int
    ): Long

    private external fun nativeTranscribe(handle: Long, samples: FloatArray): String
    private external fun nativeTranscribeFile(handle: Long, wavPath: String, useVad: Boolean): String
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
