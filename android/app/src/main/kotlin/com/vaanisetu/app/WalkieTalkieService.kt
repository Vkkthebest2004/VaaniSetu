package com.vaanisetu.app

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.vaanisetu.core.*
import kotlinx.coroutines.*

/**
 * Android Foreground Service that keeps the VaaniSetu mesh receiver
 * alive in the background with a persistent notification.
 *
 * This service:
 * 1. Acquires a PARTIAL_WAKE_LOCK so the CPU stays active for UDP receive.
 * 2. Starts MeshRouter listening on the configured channel.
 * 3. On incoming MicroRadioPacket, synthesizes Indic TTS and plays audio.
 * 4. Runs as a foreground service to survive Android Doze mode.
 */
class WalkieTalkieService : Service() {

    companion object {
        private const val TAG = "WTService"
        private const val NOTIFICATION_ID = 1001
        const val EXTRA_CHANNEL = "extra_channel"
        const val EXTRA_LANGUAGE = "extra_language"
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var wakeLock: PowerManager.WakeLock? = null
    private var meshRouter: MeshRouter? = null
    private var nativeTts: NativeTTS? = null
    private var audioPlayer: AudioPlayer? = null
    private var alertManager: EmergencyAlertManager? = null

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "WalkieTalkieService created")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val channel = intent?.getIntExtra(EXTRA_CHANNEL, 7) ?: 7
        val langCode = intent?.getStringExtra(EXTRA_LANGUAGE) ?: "hi"

        startForeground(NOTIFICATION_ID, buildNotification(channel))
        acquireWakeLock()
        startMeshListener(channel, langCode)

        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotification(channel: Int): Notification {
        val openIntent = Intent(this, WalkieTalkieActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, VaaniSetuApp.NOTIFICATION_CHANNEL_ID)
            .setContentTitle("VaaniSetu Active")
            .setContentText("Listening on Channel ${String.format("%02d", channel)} • 100% Offline")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setContentIntent(pendingIntent)
            .build()
    }

    private fun acquireWakeLock() {
        val powerManager = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "VaaniSetu::MeshListenerWakeLock"
        ).apply {
            acquire(10 * 60 * 1000L) // 10 minute timeout, re-acquired on each incoming packet
        }
    }

    private fun startMeshListener(channel: Int, langCode: String) {
        val modelBase = VaaniSetuApp.modelBasePath

        // Initialize TTS engine for voice playback of received messages
        nativeTts = NativeTTS().also { tts ->
            val modelDir = "$modelBase/models/tts"
            tts.init(
                modelPath = "$modelDir/en_US-lessac-low.onnx",
                tokensPath = "$modelDir/tokens.txt",
                dataDirPath = "$modelDir/espeak-ng-data"
            )
        }

        audioPlayer = AudioPlayer()
        alertManager = EmergencyAlertManager(this)

        meshRouter = MeshRouter(port = 8989, defaultChannel = channel).also { router ->
            router.startListening(serviceScope) { packet, sourceIp ->
                handleIncomingPacket(packet, sourceIp)
            }
        }

        Log.d(TAG, "Mesh listener started on channel $channel, language $langCode")
    }

    private fun handleIncomingPacket(packet: MicroRadioPacket, sourceIp: String) {
        serviceScope.launch {
            val text = packet.resolvedText
            if (text.isBlank()) return@launch

            Log.d(TAG, "Received from $sourceIp: '$text' (Ch${packet.channel}, ${packet.language.code})")

            val tts = nativeTts ?: return@launch
            val player = audioPlayer ?: return@launch

            if (packet.isEmergency) {
                alertManager?.triggerDistressAlert("[EMERGENCY] $text", tts, player)
            } else {
                val samples = tts.synthesize(text, speed = 1.0f)
                if (samples.isNotEmpty()) {
                    player.play(samples)
                }
            }

            // Re-acquire wake lock on activity
            wakeLock?.let {
                if (it.isHeld) it.release()
                it.acquire(10 * 60 * 1000L)
            }
        }
    }

    override fun onDestroy() {
        Log.d(TAG, "WalkieTalkieService destroyed")
        meshRouter?.close()
        audioPlayer?.close()
        nativeTts?.close()
        serviceScope.cancel()
        wakeLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }
}
