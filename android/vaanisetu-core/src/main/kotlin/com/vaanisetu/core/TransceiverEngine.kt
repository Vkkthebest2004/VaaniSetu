package com.vaanisetu.core

import java.io.Closeable
import kotlinx.coroutines.*

/**
 * Orchestrates the full VaaniSetu neural transceiver pipeline on Android.
 *
 * Wraps all subsystems into a single high-level API:
 *   Mic → AcousticProcessor → NativeVAD → NativeSTT → TacticalRescorer
 *   → MicroRadioPacket → MeshRouter → [Receiver] → BrahmiTransliterator
 *   → NativeTTS → EmergencySirenGenerator → AudioPlayer
 *
 * Usage:
 *   val engine = TransceiverEngine(modelBasePath)
 *   engine.initialize()
 *   engine.startListening(scope) { packet, ip -> ... }
 *   val text = engine.transcribe(audioSamples)
 *   engine.transmit(text, channel = 7, language = IndicLanguage.HINDI)
 */
class TransceiverEngine(
    private val modelBasePath: String
) : Closeable {

    val stt = NativeSTT()
    val tts = NativeTTS()
    val vad = NativeVAD()
    val recorder = AudioRecorder()
    val player = AudioPlayer()
    val meshRouter = MeshRouter(port = 8989, defaultChannel = 7)

    var currentChannel: Int = 7
        set(value) { field = value.coerceIn(1, 16); meshRouter.defaultChannel = field }
    var currentLanguage: IndicLanguage = IndicLanguage.HINDI

    val isReady: Boolean
        get() = stt.isInitialized && tts.isInitialized

    /**
     * Initialize all neural engines with model files from [modelBasePath].
     *
     * @return true if all engines initialized successfully.
     */
    fun initialize(): Boolean {
        val sttDir = "$modelBasePath/models/stt"
        val ttsDir = "$modelBasePath/models/tts"
        val vadDir = "$modelBasePath/models/vad"

        val sttOk = stt.init(
            encoderPath = "$sttDir/encoder.int8.onnx",
            decoderPath = "$sttDir/decoder.onnx",
            joinerPath = "$sttDir/joiner.int8.onnx",
            tokensPath = "$sttDir/tokens.txt",
            vadModelPath = "$vadDir/silero_vad.onnx"
        )

        val ttsOk = tts.init(
            modelPath = "$ttsDir/en_US-lessac-low.onnx",
            tokensPath = "$ttsDir/tokens.txt",
            dataDirPath = "$ttsDir/espeak-ng-data"
        )

        val vadOk = vad.init(modelPath = "$vadDir/silero_vad.onnx")

        return sttOk && ttsOk
    }

    /**
     * Run acoustic conditioning + STT transcription + tactical rescoring.
     *
     * @param rawAudio Raw 16kHz float32 PCM from microphone.
     * @return Recognized and rescored text string.
     */
    fun transcribe(rawAudio: FloatArray): String {
        if (!stt.isInitialized) return ""

        // Apply acoustic conditioning (Whisper-safe AGC, DC removal)
        val conditioned = AcousticProcessor.process(rawAudio, forWhisper = true)

        // Run on-device STT inference
        val rawText = stt.transcribe(conditioned)

        // Apply tactical domain rescoring
        return TacticalRescorer.rescore(rawText)
    }

    /**
     * Transmit text as a MicroRadioPacket over the mesh network.
     *
     * @param text Recognized speech text.
     * @param channel Radio channel (1-16).
     * @param language Indic language enum.
     */
    suspend fun transmit(
        text: String,
        channel: Int = currentChannel,
        language: IndicLanguage = currentLanguage
    ): Boolean {
        return meshRouter.sendVoiceNote(text, channel, language)
    }

    /**
     * Transmit a tactical emergency macro (6-byte total packet).
     */
    suspend fun transmitMacro(
        macro: TacticalMacro,
        channel: Int = currentChannel,
        language: IndicLanguage = currentLanguage
    ): Boolean {
        return meshRouter.sendTacticalMacro(macro, channel, language)
    }

    /**
     * Synthesize received text into spoken audio for playback.
     *
     * @param text Text to speak.
     * @param language Source language (for Brahmi transliteration).
     * @param isEmergency If true, prepend siren and boost volume.
     * @return Float32 PCM audio samples ready for AudioPlayer.
     */
    fun synthesize(
        text: String,
        language: IndicLanguage = IndicLanguage.HINDI,
        isEmergency: Boolean = false
    ): FloatArray {
        if (!tts.isInitialized) return FloatArray(0)

        // Transliterate non-Devanagari text to phonetic Devanagari for Piper VITS
        val phoneticText = BrahmiTransliterator.toDevanagariPhonetic(text, language.code)

        // Neural TTS synthesis
        val samples = tts.synthesize(phoneticText, speed = 1.0f)

        // If emergency, prepend siren with +12dB boost
        return if (isEmergency && samples.isNotEmpty()) {
            EmergencySirenGenerator.prependSirenToSpeech(
                speechSamples = samples,
                sampleRate = tts.sampleRate,
                sirenDurationSec = 1.5f,
                gainBoostDb = 12f
            )
        } else {
            samples
        }
    }

    /**
     * Start background mesh listener.
     */
    fun startMeshListener(
        scope: CoroutineScope,
        onPacketReceived: (MicroRadioPacket, String) -> Unit
    ) {
        meshRouter.startListening(scope, onPacketReceived)
    }

    override fun close() {
        recorder.close()
        player.close()
        meshRouter.close()
        stt.close()
        tts.close()
        vad.close()
    }
}
