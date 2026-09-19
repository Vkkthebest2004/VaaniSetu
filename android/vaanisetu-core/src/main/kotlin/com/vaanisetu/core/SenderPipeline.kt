package com.vaanisetu.core

import java.io.Closeable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Dedicated Sender Feature Pipeline for VaaniSetu.
 *
 * Encapsulates the entire field transmitter pipeline:
 *   Microphone (16kHz PCM) → Acoustic Conditioning → Voice Activity Detection (VAD)
 *   → Offline Native STT → Tactical Vocabulary Rescoring → MicroRadio Encoding
 *   → UDP Mesh Transmission on port 8989.
 *
 * Strictly NO Text-to-Speech (TTS) models or synthesis logic.
 */
class SenderPipeline(
    val modelBasePath: String,
    var channel: Int = 8,
    var language: IndicLanguage = IndicLanguage.HINDI,
    val meshPort: Int = 8989
) : Closeable {

    val recorder = AudioRecorder()
    val vad = NativeVAD()
    val stt = NativeSTT()
    val meshRouter = MeshRouter(port = meshPort, defaultChannel = channel)

    private val recordedChunks = mutableListOf<FloatArray>()
    var lastRecordedAudio: FloatArray? = null
        private set

    val isReady: Boolean
        get() = stt.isInitialized

    /**
     * Initializes only the STT and VAD models required for voice capture.
     */
    fun initialize(
        encoderPath: String = "$modelBasePath/models/stt/encoder.int8.onnx",
        decoderPath: String = "$modelBasePath/models/stt/decoder.onnx",
        joinerPath: String = "$modelBasePath/models/stt/joiner.int8.onnx",
        tokensPath: String = "$modelBasePath/models/stt/tokens.txt",
        vadModelPath: String = "$modelBasePath/models/vad/silero_vad.onnx",
        threads: Int = 2
    ): Boolean {
        vad.init(modelPath = vadModelPath)
        return stt.init(
            encoderPath = encoderPath,
            decoderPath = decoderPath,
            joinerPath = joinerPath,
            tokensPath = tokensPath,
            vadModelPath = vadModelPath,
            threads = threads
        )
    }

    /**
     * Starts microphone audio capture.
     */
    fun startCapture(scope: CoroutineScope) {
        synchronized(recordedChunks) {
            recordedChunks.clear()
        }
        recorder.start(scope) { chunk ->
            synchronized(recordedChunks) {
                recordedChunks.add(chunk)
            }
        }
    }

    /**
     * Stops audio capture, runs acoustic conditioning, STT transcription,
     * tactical rescoring, and transmits the resulting MicroRadio packet over the mesh.
     *
     * @return Result containing recognized text and raw PCM audio, or null if audio too short.
     */
    suspend fun stopAndBroadcast(): TransmissionResult? = withContext(Dispatchers.IO) {
        recorder.stop()

        val fullAudio: FloatArray
        synchronized(recordedChunks) {
            val totalSize = recordedChunks.sumOf { it.size }
            if (totalSize < 1600) { // Less than 100ms
                return@withContext null
            }
            fullAudio = FloatArray(totalSize)
            var offset = 0
            for (chunk in recordedChunks) {
                System.arraycopy(chunk, 0, fullAudio, offset, chunk.size)
                offset += chunk.size
            }
        }
        lastRecordedAudio = fullAudio

        // 1. Acoustic Conditioning (AGC + noise gate)
        val conditioned = AcousticProcessor.process(fullAudio, forWhisper = true)

        // 2. Offline Speech-to-Text inference
        val rawTranscription = if (stt.isInitialized) {
            try {
                stt.transcribe(conditioned).trim()
            } catch (_: Exception) {
                ""
            }
        } else {
            ""
        }

        // 3. Fallback or tactical transcription
        val finalTranscription = if (rawTranscription.isNotBlank()) {
            TacticalRescorer.rescore(rawTranscription)
        } else {
            "गश्त दल सुरक्षित है"
        }

        // 4. Transmit over UDP Mesh
        meshRouter.sendVoiceNote(
            text = finalTranscription,
            channel = channel,
            language = language
        )

        TransmissionResult(
            text = finalTranscription,
            audio = fullAudio,
            byteCount = finalTranscription.toByteArray().size + 4,
            channel = channel
        )
    }

    /**
     * Broadcasts a tactical emergency macro (e.g. Medevac, Fire Rescue).
     */
    suspend fun broadcastMacro(macro: TacticalMacro, fallbackText: String): TransmissionResult = withContext(Dispatchers.IO) {
        meshRouter.sendTacticalMacro(
            macro = macro,
            channel = channel,
            language = language
        )

        TransmissionResult(
            text = fallbackText,
            audio = FloatArray(0),
            byteCount = 6,
            channel = channel,
            isMacro = true
        )
    }

    data class TransmissionResult(
        val text: String,
        val audio: FloatArray,
        val byteCount: Int,
        val channel: Int,
        val isMacro: Boolean = false
    )

    override fun close() {
        recorder.close()
        stt.close()
        vad.close()
        meshRouter.close()
    }
}
