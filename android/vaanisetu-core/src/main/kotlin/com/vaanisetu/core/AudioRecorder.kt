package com.vaanisetu.core

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.*
import java.io.Closeable
import kotlin.math.sqrt

/**
 * Low-latency audio capture using Android AudioRecord.
 * Records 16 kHz, 16-bit mono PCM audio for speech recognition.
 */
class AudioRecorder(
    private val sampleRate: Int = 16000,
    private val bufferSizeMs: Int = 100
) : Closeable {

    private var audioRecord: AudioRecord? = null
    private var recordingJob: Job? = null
    @Volatile
    var isRecording: Boolean = false
        private set

    private val minBufferSize = AudioRecord.getMinBufferSize(
        sampleRate,
        AudioFormat.CHANNEL_IN_MONO,
        AudioFormat.ENCODING_PCM_16BIT
    )

    private val chunkSize = (sampleRate * bufferSizeMs / 1000)

    @SuppressLint("MissingPermission")
    fun start(scope: CoroutineScope, onAudioChunk: (FloatArray) -> Unit) {
        if (isRecording) return

        val bufferSize = maxOf(minBufferSize, chunkSize * 2)
        val record = AudioRecord(
            MediaRecorder.AudioSource.VOICE_RECOGNITION,
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize
        )

        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            throw IllegalStateException("Failed to initialize AudioRecord")
        }

        audioRecord = record
        record.startRecording()
        isRecording = true

        recordingJob = scope.launch(Dispatchers.IO) {
            val shortBuffer = ShortArray(chunkSize)
            val floatBuffer = FloatArray(chunkSize)

            while (isActive && isRecording) {
                val read = record.read(shortBuffer, 0, chunkSize)
                if (read > 0) {
                    for (i in 0 until read) {
                        floatBuffer[i] = shortBuffer[i] / 32768.0f
                    }
                    val chunk = if (read == chunkSize) floatBuffer.clone() else floatBuffer.copyOf(read)
                    onAudioChunk(chunk)
                }
            }
        }
    }

    fun stop() {
        isRecording = false
        recordingJob?.cancel()
        recordingJob = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            // Ignore on teardown
        }
        audioRecord = null
    }

    override fun close() {
        stop()
    }

    companion object {
        fun calculateRms(samples: FloatArray): Float {
            if (samples.isEmpty()) return 0f
            var sum = 0f
            for (s in samples) {
                sum += s * s
            }
            return sqrt(sum / samples.size)
        }
    }
}
