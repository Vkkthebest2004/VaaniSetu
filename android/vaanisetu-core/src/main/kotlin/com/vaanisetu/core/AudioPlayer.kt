package com.vaanisetu.core

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.Closeable
import kotlin.math.max
import kotlin.math.min

/**
 * Low-latency audio playback using Android AudioTrack.
 * Plays float32 or 16-bit PCM audio through speakers.
 */
class AudioPlayer(
    private val sampleRate: Int = 16000
) : Closeable {

    private var audioTrack: AudioTrack? = null

    private fun getOrCreateTrack(): AudioTrack {
        audioTrack?.let { return it }

        val minBufferSize = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )

        val track = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(maxOf(minBufferSize, 4096))
            .setTransferMode(AudioTrack.MODE_STREAM)
            .build()

        track.play()
        audioTrack = track
        return track
    }

    /**
     * Play float32 audio samples [-1.0f, 1.0f] on background thread.
     */
    suspend fun play(samples: FloatArray) = withContext(Dispatchers.IO) {
        if (samples.isEmpty()) return@withContext

        val track = getOrCreateTrack()
        val shortBuffer = ShortArray(samples.size)

        for (i in samples.indices) {
            val clamped = max(-1.0f, min(1.0f, samples[i]))
            shortBuffer[i] = (clamped * 32767.0f).toInt().toShort()
        }

        track.write(shortBuffer, 0, shortBuffer.size)
    }

    fun stop() {
        try {
            audioTrack?.pause()
            audioTrack?.flush()
            audioTrack?.stop()
            audioTrack?.release()
        } catch (e: Exception) {
            // Ignore
        }
        audioTrack = null
    }

    override fun close() {
        stop()
    }
}
