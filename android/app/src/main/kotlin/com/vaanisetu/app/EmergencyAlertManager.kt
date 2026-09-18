package com.vaanisetu.app

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.os.Build
import android.os.CombinedVibration
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import com.vaanisetu.core.AudioPlayer
import com.vaanisetu.core.NativeTTS

/**
 * Manages Emergency Distress Alerts on Android:
 * - Overrides system volume to 100% (non-interruptible).
 * - Triggers continuous emergency tactile vibration.
 * - Broadcasts spoken alert at maximum loudness.
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

    /**
     * Trigger urgent distress alarm: forces maximum volume and plays non-interruptible voice alert.
     */
    suspend fun triggerDistressAlert(
        alertText: String,
        nativeTts: NativeTTS,
        audioPlayer: AudioPlayer
    ) {
        // 1. Force maximum alarm volume
        val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_ALARM)
        audioManager.setStreamVolume(AudioManager.STREAM_ALARM, maxVolume, AudioManager.FLAG_SHOW_UI)

        // 2. SOS Vibration pattern (dot-dot-dot dash-dash-dash dot-dot-dot)
        val sosPattern = longArrayOf(0, 150, 100, 150, 100, 150, 200, 400, 100, 400, 100, 400, 200, 150, 100, 150)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(VibrationEffect.createWaveform(sosPattern, -1))
        } else {
            @Suppress("DEPRECATION")
            vibrator?.vibrate(sosPattern, -1)
        }

        // 3. Synthesize alert text with boosted speed and play
        val alertSamples = nativeTts.synthesize(alertText, speed = 1.15f)
        if (alertSamples.isNotEmpty()) {
            audioPlayer.play(alertSamples)
        }
    }

    fun cancelAlarm() {
        vibrator?.cancel()
    }
}
