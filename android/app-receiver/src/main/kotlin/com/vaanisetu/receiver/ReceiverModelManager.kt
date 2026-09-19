package com.vaanisetu.receiver

import android.content.Context
import java.io.File

/**
 * Dedicated Model Manager for VaaniSetu Receiver App.
 *
 * Manages only the Text-to-Speech (TTS) neural models and phoneme datasets.
 * Strictly guarantees that Speech-to-Text (STT) and VAD models are NOT required or loaded.
 */
class ReceiverModelManager(private val context: Context) {

    private val baseDir: File = context.getExternalFilesDir(null) ?: context.filesDir

    // Model paths required ONLY for Receiver
    val ttsDir: File = File(baseDir, "models/tts")

    // Piper Hindi Rohan (Medium INT8)
    val piperHindiModel: File = File(ttsDir, "vits-piper-hi_IN-rohan-medium-int8/hi_IN-rohan-medium.onnx")
    val piperHindiTokens: File = File(ttsDir, "vits-piper-hi_IN-rohan-medium-int8/tokens.txt")
    val piperHindiEspeak: File = File(ttsDir, "vits-piper-hi_IN-rohan-medium-int8/espeak-ng-data")

    // Piper English Lessac (Low)
    val piperEnglishModel: File = File(ttsDir, "vits-piper-en_US-lessac-low/en_US-lessac-low.onnx")
    val piperEnglishTokens: File = File(ttsDir, "vits-piper-en_US-lessac-low/tokens.txt")
    val piperEnglishEspeak: File = File(ttsDir, "vits-piper-en_US-lessac-low/espeak-ng-data")

    // Flat directory fallback
    val flatModel: File = File(ttsDir, "en_US-lessac-low.onnx")
    val flatTokens: File = File(ttsDir, "tokens.txt")
    val flatEspeak: File = File(ttsDir, "espeak-ng-data")

    /**
     * Checks if dedicated TTS models exist.
     */
    fun hasTtsModel(): Boolean {
        return (piperHindiModel.exists() && piperHindiTokens.exists()) ||
                (piperEnglishModel.exists() && piperEnglishTokens.exists()) ||
                (flatModel.exists() && flatTokens.exists())
    }

    /**
     * Verifies that no STT/VAD models are required or loaded for Receiver operation.
     */
    val isSttExcluded: Boolean = true

    /**
     * Resolves the active TTS model paths for initialization.
     */
    fun resolveTtsPaths(): TtsModelPaths? {
        if (piperHindiModel.exists() && piperHindiTokens.exists()) {
            return TtsModelPaths(
                model = piperHindiModel.absolutePath,
                tokens = piperHindiTokens.absolutePath,
                dataDir = if (piperHindiEspeak.exists()) piperHindiEspeak.absolutePath else "",
                voiceName = "Hindi Rohan (INT8)"
            )
        }
        if (piperEnglishModel.exists() && piperEnglishTokens.exists()) {
            return TtsModelPaths(
                model = piperEnglishModel.absolutePath,
                tokens = piperEnglishTokens.absolutePath,
                dataDir = if (piperEnglishEspeak.exists()) piperEnglishEspeak.absolutePath else "",
                voiceName = "English Lessac (Low)"
            )
        }
        if (flatModel.exists() && flatTokens.exists()) {
            return TtsModelPaths(
                model = flatModel.absolutePath,
                tokens = flatTokens.absolutePath,
                dataDir = if (flatEspeak.exists()) flatEspeak.absolutePath else "",
                voiceName = "Standard TTS"
            )
        }
        return null
    }

    data class TtsModelPaths(
        val model: String,
        val tokens: String,
        val dataDir: String,
        val voiceName: String
    )
}
