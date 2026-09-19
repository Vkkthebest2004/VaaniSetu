package com.vaanisetu.core

import java.io.Closeable
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Dedicated Receiver Feature Pipeline for VaaniSetu.
 *
 * Encapsulates the entire command listening station pipeline:
 *   UDP Mesh Socket Listener (Port 8989) → MicroRadio Packet CRC-16 Verification
 *   → Macro/Voice Decoding → Brahmi Script Transliterator
 *   → Offline Indic Neural TTS (Piper VITS) → Warble Emergency Siren
 *   → Low-latency AudioTrack Player.
 *
 * Strictly NO Microphone AudioRecord or Speech-to-Text (STT) models.
 */
class ReceiverPipeline(
    val modelBasePath: String,
    var channel: Int = 8,
    val meshPort: Int = 8989
) : Closeable {

    val tts = NativeTTS()
    val player = AudioPlayer()
    val meshRouter = MeshRouter(port = meshPort, defaultChannel = channel)

    var isAutoTtsEnabled: Boolean = true
    var lastReceivedAudio: FloatArray? = null
        private set

    val isReady: Boolean
        get() = tts.isInitialized

    /**
     * Initializes only the Piper VITS TTS model required for neural voice synthesis.
     */
    fun initialize(
        modelPath: String = "$modelBasePath/models/tts/en_US-lessac-low.onnx",
        tokensPath: String = "$modelBasePath/models/tts/tokens.txt",
        dataDirPath: String = "$modelBasePath/models/tts/espeak-ng-data",
        threads: Int = 2
    ): Boolean {
        return tts.init(
            modelPath = modelPath,
            tokensPath = tokensPath,
            dataDirPath = dataDirPath,
            threads = threads
        )
    }

    /**
     * Starts listening for RF MicroRadio packets over the UDP mesh socket.
     */
    fun startListening(
        scope: CoroutineScope,
        onPacketReceived: (packet: MicroRadioPacket, sourceIp: String) -> Unit
    ) {
        meshRouter.startListening(scope) { packet, sourceIp ->
            onPacketReceived(packet, sourceIp)
        }
    }

    /**
     * Processes an incoming decoded packet: transliterates if needed, synthesizes neural voice,
     * or sounds emergency siren if flagged.
     */
    suspend fun processAndPlay(
        packet: MicroRadioPacket,
        speed: Float = 1.0f
    ): AudioResult = withContext(Dispatchers.IO) {
        val text = packet.resolvedText
        if (text.isBlank()) {
            return@withContext AudioResult(FloatArray(0), isEmergency = packet.isEmergency)
        }

        // Emergency warble siren
        val sirenAudio = if (packet.isEmergency) {
            EmergencySirenGenerator.generateSiren(durationSec = 1.2f)
        } else {
            FloatArray(0)
        }

        // Neural speech synthesis
        val voiceAudio = if (tts.isInitialized) {
            try {
                tts.synthesize(text, speed = speed)
            } catch (_: Exception) {
                FloatArray(0)
            }
        } else {
            FloatArray(0)
        }

        // Concatenate siren + voice if emergency
        val combinedAudio = if (sirenAudio.isNotEmpty() && voiceAudio.isNotEmpty()) {
            FloatArray(sirenAudio.size + voiceAudio.size).also { combined ->
                System.arraycopy(sirenAudio, 0, combined, 0, sirenAudio.size)
                System.arraycopy(voiceAudio, 0, combined, sirenAudio.size, voiceAudio.size)
            }
        } else if (voiceAudio.isNotEmpty()) {
            voiceAudio
        } else {
            sirenAudio
        }

        lastReceivedAudio = combinedAudio

        if (isAutoTtsEnabled && combinedAudio.isNotEmpty()) {
            player.play(combinedAudio)
        }

        AudioResult(
            samples = combinedAudio,
            isEmergency = packet.isEmergency
        )
    }

    /**
     * Replays the last received and synthesized audio through the speaker.
     */
    suspend fun replayLastAudio() = withContext(Dispatchers.IO) {
        lastReceivedAudio?.let { samples ->
            if (samples.isNotEmpty()) {
                player.play(samples)
            }
        }
    }

    data class AudioResult(
        val samples: FloatArray,
        val isEmergency: Boolean
    )

    override fun close() {
        tts.close()
        player.close()
        meshRouter.close()
    }
}
