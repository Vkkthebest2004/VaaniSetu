package com.vaanisetu.receiver

import android.content.Context
import android.media.AudioManager
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import com.vaanisetu.core.AudioPlayer
import com.vaanisetu.core.EmergencySirenGenerator
import com.vaanisetu.core.NativeTTS

/**
 * Dedicated Emergency Distress Alert Manager for VaaniSetu Receiver Station.
 *
 * Sounds the loud tactical warble siren via EmergencySirenGenerator,
 * vibrates the station device with the SOS pattern, and announces the emergency
 * verbally through the Indic Neural TTS engine.
 */
class EmergencyAlertManager(private val context: Context) {

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val vibrator: Vibrator? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        val vibratorManager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
        vibratorManager?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
    }

    suspend fun triggerDistressAlert(
        alertText: String,
        nativeTts: NativeTTS,
        audioPlayer: AudioPlayer
    ) {
        val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
        audioManager.setStreamVolume(AudioManager.STREAM_ALARM, maxVolume, AudioManager.FLAG_SHOW_UI)

        // 1. SOS Haptic pattern
        val sosPattern = longArrayOf(0, 150, 100, 150, 100, 150, 200, 400, 100, 400, 100, 400, 200, 150, 100, 150)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(VibrationEffect.createWaveform(sosPattern, -1))
        } else {
            @Suppress("DEPRECATION")
            vibrator?.vibrate(sosPattern, -1)
        }

        // 2. High-priority warble siren
        val sirenSamples = EmergencySirenGenerator.generateSiren(durationSec = 1.2f)
        if (sirenSamples.isNotEmpty()) {
            audioPlayer.play(sirenSamples)
        }

        // 3. Indic Neural Voice Readout
        if (nativeTts.isInitialized) {
            val alertSamples = nativeTts.synthesize(alertText, speed = 1.1f)
            if (alertSamples.isNotEmpty()) {
                audioPlayer.play(alertSamples)
            }
        }
    }

    fun cancelAlarm() {
        vibrator?.cancel()
    }
}
