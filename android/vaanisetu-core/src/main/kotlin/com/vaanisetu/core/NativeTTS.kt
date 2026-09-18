package com.vaanisetu.core

import java.io.Closeable

/**
 * Native Text-to-Speech Engine wrapper for Android.
 *
 * Interfaces directly with the C++ sherpa-onnx Piper VITS core via JNI
 * for zero-overhead, ultra-fast speech synthesis on low-end ARM devices.
 */
class NativeTTS : Closeable {

    private var nativeHandle: Long = 0

    val isInitialized: Boolean
        get() = nativeHandle != 0L

    val sampleRate: Int
        get() = if (isInitialized) nativeGetSampleRate(nativeHandle) else 16000

    /**
     * Initialize the native TTS engine with Piper VITS model paths.
     */
    fun init(
        modelPath: String,
        tokensPath: String,
        dataDirPath: String = "",
        threads: Int = 2
    ): Boolean {
        if (isInitialized) {
            close()
        }
        nativeHandle = nativeInit(
            model = modelPath,
            tokens = tokensPath,
            dataDir = dataDirPath,
            threads = threads
        )
        return nativeHandle != 0L
    }

    /**
     * Synthesize text to float32 audio samples [-1.0f, 1.0f].
     */
    fun synthesize(text: String, speed: Float = 1.0f): FloatArray {
        check(isInitialized) { "NativeTTS engine is not initialized" }
        return nativeSynthesize(nativeHandle, text, speed)
    }

    /**
     * Synthesize text and write directly to a WAV file.
     * Returns audio duration in seconds.
     */
    fun synthesizeToFile(text: String, outputPath: String, speed: Float = 1.0f): Float {
        check(isInitialized) { "NativeTTS engine is not initialized" }
        return nativeSynthesizeToFile(nativeHandle, text, outputPath, speed)
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
        model: String,
        tokens: String,
        dataDir: String,
        threads: Int
    ): Long

    private external fun nativeSynthesize(handle: Long, text: String, speed: Float): FloatArray
    private external fun nativeSynthesizeToFile(handle: Long, text: String, outputPath: String, speed: Float): Float
    private external fun nativeGetSampleRate(handle: Long): Int
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
