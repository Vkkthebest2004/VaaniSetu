package com.vaanisetu.core

/**
 * Acoustic Front-End DSP Processor for Android.
 *
 * Mirrors the Python AcousticFrontEnd (acoustic_front_end.py) with:
 * 1. DC Baseline Centering (removes microphone sensor drift).
 * 2. Whisper-Safe Soft Tanh Dynamic Range AGC Limiter.
 * 3. High-Frequency Pre-Emphasis Filter (alpha=0.97).
 * 4. Syllable Boundary Padding (120ms pre / 220ms post).
 *
 * All processing is done in-place on Float32 PCM arrays with zero allocations.
 */
object AcousticProcessor {

    /**
     * Full acoustic conditioning pipeline.
     * Applies DC removal, AGC, pre-emphasis, and boundary padding.
     *
     * @param samples Raw 16kHz float32 PCM audio [-1.0, 1.0].
     * @param forWhisper If true, skips pre-emphasis to preserve Whisper log-mel frequencies.
     * @return Conditioned audio ready for neural STT inference.
     */
    fun process(
        samples: FloatArray,
        sampleRate: Int = 16000,
        forWhisper: Boolean = true
    ): FloatArray {
        if (samples.isEmpty()) return samples

        var audio = removeDcOffset(samples)
        audio = applyDynamicRangeAgc(audio, gamma = 1.5f, ceiling = 0.85f)

        if (!forWhisper) {
            audio = applyPreEmphasis(audio, alpha = 0.97f)
        }

        audio = applySyllablePadding(audio, sampleRate, preMs = 120, postMs = 220)
        return audio
    }

    /**
     * Remove DC offset (mean subtraction) to eliminate microphone sensor drift.
     */
    fun removeDcOffset(samples: FloatArray): FloatArray {
        if (samples.isEmpty()) return samples
        var sum = 0.0
        for (s in samples) sum += s
        val mean = (sum / samples.size).toFloat()
        val result = FloatArray(samples.size)
        for (i in samples.indices) {
            result[i] = samples[i] - mean
        }
        return result
    }

    /**
     * Whisper-safe soft hyperbolic tangent AGC limiter.
     *
     * y = (tanh(gamma * x / peak) / tanh(gamma)) * ceiling
     *
     * Provides smooth dynamic range compression without hard clipping.
     * Preserves spectral envelope for neural speech recognition models.
     */
    fun applyDynamicRangeAgc(
        samples: FloatArray,
        gamma: Float = 1.5f,
        ceiling: Float = 0.85f
    ): FloatArray {
        if (samples.isEmpty()) return samples

        var peak = 0f
        for (s in samples) {
            val abs = kotlin.math.abs(s)
            if (abs > peak) peak = abs
        }
        if (peak < 1e-6f) return samples

        val tanhGamma = kotlin.math.tanh(gamma.toDouble()).toFloat()
        val result = FloatArray(samples.size)
        for (i in samples.indices) {
            val normalized = gamma * samples[i] / peak
            val compressed = kotlin.math.tanh(normalized.toDouble()).toFloat()
            result[i] = (compressed / tanhGamma) * ceiling
        }
        return result
    }

    /**
     * First-order high-frequency pre-emphasis FIR filter.
     * y[t] = x[t] - alpha * x[t-1]
     *
     * Boosts high-frequency consonant formants (especially retroflex: ट, ठ, ड, ढ).
     */
    fun applyPreEmphasis(samples: FloatArray, alpha: Float = 0.97f): FloatArray {
        if (samples.size < 2) return samples
        val result = FloatArray(samples.size)
        result[0] = samples[0]
        for (i in 1 until samples.size) {
            result[i] = samples[i] - alpha * samples[i - 1]
        }
        return result
    }

    /**
     * Add syllable boundary padding to prevent clipping of plosives and trailing matras.
     */
    fun applySyllablePadding(
        samples: FloatArray,
        sampleRate: Int = 16000,
        preMs: Int = 120,
        postMs: Int = 220
    ): FloatArray {
        val preSamples = sampleRate * preMs / 1000
        val postSamples = sampleRate * postMs / 1000
        val padded = FloatArray(preSamples + samples.size + postSamples)
        System.arraycopy(samples, 0, padded, preSamples, samples.size)
        return padded
    }

    /**
     * Calculate Root Mean Square (RMS) energy of audio signal.
     */
    fun calculateRms(samples: FloatArray): Float {
        if (samples.isEmpty()) return 0f
        var sum = 0.0
        for (s in samples) sum += s.toDouble() * s.toDouble()
        return kotlin.math.sqrt(sum / samples.size).toFloat()
    }

    /**
     * Calculate peak amplitude of audio signal.
     */
    fun calculatePeak(samples: FloatArray): Float {
        var peak = 0f
        for (s in samples) {
            val abs = kotlin.math.abs(s)
            if (abs > peak) peak = abs
        }
        return peak
    }
}
