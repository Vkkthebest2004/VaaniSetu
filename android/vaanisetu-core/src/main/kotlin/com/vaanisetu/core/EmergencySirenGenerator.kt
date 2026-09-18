package com.vaanisetu.core

import kotlin.math.PI
import kotlin.math.sin

/**
 * Emergency Siren Audio Generator for Android.
 *
 * Synthesizes a dual-tone warble siren (960 Hz / 770 Hz alternating)
 * that is prepended to emergency alert voice messages.
 *
 * The siren is non-interruptible and plays at +12dB above normal volume.
 */
object EmergencySirenGenerator {

    private const val TONE_A_HZ = 960.0
    private const val TONE_B_HZ = 770.0
    private const val WARBLE_RATE_HZ = 3.5  // alternations per second

    /**
     * Generate a dual-tone emergency siren waveform.
     *
     * @param durationSec Duration of the siren in seconds.
     * @param sampleRate Audio sample rate (default 16000 Hz).
     * @param amplitude Peak amplitude [0.0, 1.0].
     * @return Float32 PCM audio samples.
     */
    fun generateSiren(
        durationSec: Float = 1.5f,
        sampleRate: Int = 16000,
        amplitude: Float = 0.85f
    ): FloatArray {
        val numSamples = (sampleRate * durationSec).toInt()
        val samples = FloatArray(numSamples)
        val twoPi = 2.0 * PI

        for (i in 0 until numSamples) {
            val t = i.toDouble() / sampleRate
            // Alternate between tone A and tone B at warble rate
            val warblePhase = sin(twoPi * WARBLE_RATE_HZ * t)
            val freq = if (warblePhase >= 0) TONE_A_HZ else TONE_B_HZ
            samples[i] = (amplitude * sin(twoPi * freq * t)).toFloat()
        }

        // Apply fade-in (50ms) and fade-out (100ms) to avoid click artifacts
        val fadeInSamples = (sampleRate * 0.05).toInt()
        val fadeOutSamples = (sampleRate * 0.1).toInt()
        for (i in 0 until fadeInSamples.coerceAtMost(numSamples)) {
            samples[i] *= i.toFloat() / fadeInSamples
        }
        for (i in 0 until fadeOutSamples.coerceAtMost(numSamples)) {
            val idx = numSamples - 1 - i
            samples[idx] *= i.toFloat() / fadeOutSamples
        }

        return samples
    }

    /**
     * Prepend emergency siren to a synthesized voice message.
     *
     * @param speechSamples TTS-synthesized alert speech.
     * @param sampleRate Audio sample rate.
     * @param sirenDurationSec Duration of siren preamble.
     * @param gainBoostDb Digital gain boost in decibels (default +12dB).
     * @return Combined siren + boosted speech audio.
     */
    fun prependSirenToSpeech(
        speechSamples: FloatArray,
        sampleRate: Int = 16000,
        sirenDurationSec: Float = 1.5f,
        gainBoostDb: Float = 12f
    ): FloatArray {
        val siren = generateSiren(sirenDurationSec, sampleRate, amplitude = 0.85f)

        // Calculate linear gain from dB boost
        val linearGain = Math.pow(10.0, gainBoostDb / 20.0).toFloat()

        // Apply gain boost to speech and soft-clip
        val boostedSpeech = FloatArray(speechSamples.size)
        for (i in speechSamples.indices) {
            val amplified = speechSamples[i] * linearGain
            // Soft tanh clipping to prevent DAC overflow
            boostedSpeech[i] = kotlin.math.tanh(amplified.toDouble()).toFloat() * 0.95f
        }

        // Concatenate: [siren] + [silence gap 100ms] + [boosted speech]
        val gapSamples = sampleRate / 10
        val combined = FloatArray(siren.size + gapSamples + boostedSpeech.size)
        System.arraycopy(siren, 0, combined, 0, siren.size)
        System.arraycopy(boostedSpeech, 0, combined, siren.size + gapSamples, boostedSpeech.size)

        return combined
    }
}
