package com.vaanisetu.sender

import android.content.Context
import android.media.AudioManager
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import com.vaanisetu.core.AudioPlayer
import com.vaanisetu.core.EmergencySirenGenerator

/**
 * Dedicated Emergency Distress Alert Manager for VaaniSetu Sender.
 *
 * Sounds high-priority hardware warble siren and triggers tactile Morse SOS vibration.
 * Operates purely with algorithmic waveform generation — zero TTS neural model required.
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
        audioPlayer: AudioPlayer,
        durationSec: Float = 1.0f
    ) {
        val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
        audioManager.setStreamVolume(AudioManager.STREAM_ALARM, maxVolume, AudioManager.FLAG_SHOW_UI)

        val sosPattern = longArrayOf(0, 150, 100, 150, 100, 150, 200, 400, 100, 400, 100, 400, 200, 150, 100, 150)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(VibrationEffect.createWaveform(sosPattern, -1))
        } else {
            @Suppress("DEPRECATION")
            vibrator?.vibrate(sosPattern, -1)
        }

        // Generate high-intensity emergency warble tone mathematically (zero neural model needed)
        val sirenTone = EmergencySirenGenerator.generateSiren(durationSec = durationSec)
        if (sirenTone.isNotEmpty()) {
            audioPlayer.play(sirenTone)
        }
    }

    fun cancelAlarm() {
        vibrator?.cancel()
    }
}
