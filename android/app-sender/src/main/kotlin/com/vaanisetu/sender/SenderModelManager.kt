package com.vaanisetu.sender

import android.content.Context
import java.io.File

/**
 * Dedicated Model Manager for VaaniSetu Sender App.
 *
 * Manages only the Speech-to-Text (STT) and Voice Activity Detection (VAD) models.
 * Strictly guarantees that Text-to-Speech (TTS) models are NOT required or loaded.
 */
class SenderModelManager(private val context: Context) {

    private val baseDir: File = context.getExternalFilesDir(null) ?: context.filesDir

    // Model paths required ONLY for Sender
    val sttDir: File = File(baseDir, "models/stt")
    val vadDir: File = File(baseDir, "models/vad")
    val indicAdapterDir: File = File(baseDir, "models/indic_adapter")

    val vadModelFile: File = File(vadDir, "silero_vad.onnx")

    // Potential STT model permutations (Whisper Tiny or Zipformer Small)
    val whisperEncoderInt8: File = File(sttDir, "sherpa-onnx-whisper-tiny/tiny-encoder.int8.onnx")
    val whisperDecoderInt8: File = File(sttDir, "sherpa-onnx-whisper-tiny/tiny-decoder.int8.onnx")
    val whisperTokens: File = File(sttDir, "sherpa-onnx-whisper-tiny/tiny-tokens.txt")

    val zipformerEncoder: File = File(sttDir, "encoder.int8.onnx")
    val zipformerDecoder: File = File(sttDir, "decoder.onnx")
    val zipformerJoiner: File = File(sttDir, "joiner.int8.onnx")
    val zipformerTokens: File = File(sttDir, "tokens.txt")

    /**
     * Checks if dedicated STT models exist.
     */
    fun hasSttModel(): Boolean {
        return (whisperEncoderInt8.exists() && whisperDecoderInt8.exists() && whisperTokens.exists()) ||
                (zipformerEncoder.exists() && zipformerDecoder.exists() && zipformerTokens.exists())
    }

    /**
     * Checks if dedicated VAD model exists.
     */
    fun hasVadModel(): Boolean {
        return vadModelFile.exists()
    }

    /**
     * Verifies that no TTS models are required or present for Sender operation.
     */
    val isTtsExcluded: Boolean = true

    /**
     * Resolves the active model paths for initialization.
     */
    fun resolveSttPaths(): SttModelPaths? {
        if (whisperEncoderInt8.exists() && whisperDecoderInt8.exists() && whisperTokens.exists()) {
            return SttModelPaths(
                encoder = whisperEncoderInt8.absolutePath,
                decoder = whisperDecoderInt8.absolutePath,
                joiner = "",
                tokens = whisperTokens.absolutePath,
                vad = if (vadModelFile.exists()) vadModelFile.absolutePath else "",
                modelType = "Whisper-Tiny (INT8)"
            )
        }
        if (zipformerEncoder.exists() && zipformerDecoder.exists() && zipformerTokens.exists()) {
            return SttModelPaths(
                encoder = zipformerEncoder.absolutePath,
                decoder = zipformerDecoder.absolutePath,
                joiner = if (zipformerJoiner.exists()) zipformerJoiner.absolutePath else "",
                tokens = zipformerTokens.absolutePath,
                vad = if (vadModelFile.exists()) vadModelFile.absolutePath else "",
                modelType = "Zipformer-Small (INT8)"
            )
        }
        return null
    }

    data class SttModelPaths(
        val encoder: String,
        val decoder: String,
        val joiner: String,
        val tokens: String,
        val vad: String,
        val modelType: String
    )
}
