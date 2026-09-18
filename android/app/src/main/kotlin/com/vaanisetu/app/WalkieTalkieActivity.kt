package com.vaanisetu.app

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.view.MotionEvent
import android.view.View
import android.view.animation.AnimationUtils
import android.widget.Button
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.vaanisetu.core.AudioPlayer
import com.vaanisetu.core.AudioRecorder
import com.vaanisetu.core.IndicLanguage
import com.vaanisetu.core.MeshRouter
import com.vaanisetu.core.MicroRadioPacket
import com.vaanisetu.core.NativeSTT
import com.vaanisetu.core.NativeTTS
import com.vaanisetu.core.P2PTransport
import com.vaanisetu.core.TacticalMacro
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Ultra-Clean Tactical Walkie-Talkie Activity.
 *
 * Implements:
 * - Minimalist front face with 1-tap TX (Sender) / RX (Receiver) mode toggle.
 * - Massive 3D hero PTT button with breathing halo and depression animations.
 * - Single floating message card with instant audio replay and airtime telemetry.
 * - Clean bottom dock for Tactical Macros sheet, quick Ingress testing, and SOS distress.
 */
class WalkieTalkieActivity : AppCompatActivity() {

    private val nativeStt = NativeSTT()
    private val nativeTts = NativeTTS()
    private val audioRecorder = AudioRecorder()
    private val audioPlayer = AudioPlayer()
    private val p2pTransport = P2PTransport(port = 8988)
    private val meshRouter = MeshRouter(port = 8989, defaultChannel = 8)
    private lateinit var alertManager: EmergencyAlertManager

    private var currentChannel: Int = 8
    private var isTxMode: Boolean = true // true = TX (Talk), false = RX (Listen)
    private var isEmergencyDistressActive: Boolean = false
    private val recordedAudioChunks = mutableListOf<FloatArray>()
    private var lastReceivedAudio: FloatArray? = null

    // UI View References
    private lateinit var btnPrevChannel: Button
    private lateinit var btnNextChannel: Button
    private lateinit var tvChannelHeader: TextView
    private lateinit var btnModeToggle: Button

    private lateinit var viewPttHalo: View
    private lateinit var btnPtt3d: ImageButton
    private lateinit var tvPttStatus: TextView
    private lateinit var tvModeHint: TextView

    private lateinit var tvMsgHeader: TextView
    private lateinit var tvMsgText: TextView
    private lateinit var tvMsgTelemetry: TextView
    private lateinit var btnReplayAudio: ImageButton

    private lateinit var btnDockMacros: Button
    private lateinit var btnDockTest: Button
    private lateinit var btnDockSos: Button

    private val channelFrequencies = mapOf(
        1 to "433.050", 2 to "433.150", 3 to "433.250", 4 to "433.350",
        5 to "433.450", 6 to "433.550", 7 to "433.650", 8 to "433.750",
        9 to "433.850", 10 to "433.950", 11 to "434.050", 12 to "434.150",
        13 to "434.250", 14 to "434.350", 15 to "434.450", 16 to "434.550"
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_walkie_talkie)

        alertManager = EmergencyAlertManager(this)
        bindViews()
        setupListeners()
        checkPermissions()
        setupEngines()
        startMeshReceiver()
        updateChannelDisplay()
        updateModeUI()

        // Start breathing halo animation on PTT button
        val animHalo = AnimationUtils.loadAnimation(this, R.anim.anim_pulse_glow)
        viewPttHalo.startAnimation(animHalo)
    }

    private fun bindViews() {
        btnPrevChannel = findViewById(R.id.btn_prev_channel)
        btnNextChannel = findViewById(R.id.btn_next_channel)
        tvChannelHeader = findViewById(R.id.tv_channel_header)
        btnModeToggle = findViewById(R.id.btn_mode_toggle)

        viewPttHalo = findViewById(R.id.view_ptt_halo)
        btnPtt3d = findViewById(R.id.btn_ptt_3d)
        tvPttStatus = findViewById(R.id.tv_ptt_status)
        tvModeHint = findViewById(R.id.tv_mode_hint)

        tvMsgHeader = findViewById(R.id.tv_msg_header)
        tvMsgText = findViewById(R.id.tv_msg_text)
        tvMsgTelemetry = findViewById(R.id.tv_msg_telemetry)
        btnReplayAudio = findViewById(R.id.btn_replay_audio)

        btnDockMacros = findViewById(R.id.btn_dock_macros)
        btnDockTest = findViewById(R.id.btn_dock_test)
        btnDockSos = findViewById(R.id.btn_dock_sos)
    }

    private fun setupListeners() {
        // Channel Switching
        btnPrevChannel.setOnClickListener {
            currentChannel = if (currentChannel > 1) currentChannel - 1 else 16
            updateChannelDisplay()
        }
        btnNextChannel.setOnClickListener {
            currentChannel = if (currentChannel < 16) currentChannel + 1 else 1
            updateChannelDisplay()
        }

        // 1-Tap Mode Toggle (TX / RX)
        btnModeToggle.setOnClickListener {
            isTxMode = !isTxMode
            updateModeUI()
            triggerHapticClick()
        }

        // Massive Center PTT / Audio Replay Button
        btnPtt3d.setOnTouchListener { view, motionEvent ->
            if (isTxMode) {
                // In TX Mode: Push-To-Talk Microphone
                when (motionEvent.action) {
                    MotionEvent.ACTION_DOWN -> {
                        val pressAnim = AnimationUtils.loadAnimation(this, R.anim.anim_ptt_press)
                        view.startAnimation(pressAnim)
                        triggerHapticClick()
                        tvPttStatus.text = "TRANSMITTING LIVE VOICE..."
                        tvPttStatus.setTextColor(Color.parseColor("#00E676"))
                        onPttDown()
                        true
                    }
                    MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                        val releaseAnim = AnimationUtils.loadAnimation(this, R.anim.anim_ptt_release)
                        view.startAnimation(releaseAnim)
                        tvPttStatus.text = "HOLD TO TALK"
                        tvPttStatus.setTextColor(Color.parseColor("#E5A93C"))
                        onPttUp()
                        true
                    }
                    else -> false
                }
            } else {
                // In RX Mode: Tap to Replay Audio
                if (motionEvent.action == MotionEvent.ACTION_UP) {
                    replayLastAudio()
                }
                true
            }
        }

        // Replay button on message card
        btnReplayAudio.setOnClickListener {
            replayLastAudio()
        }

        // Tactical Macros Bottom Sheet
        btnDockMacros.setOnClickListener {
            showMacrosBottomSheet()
        }

        // Simulated Field Ingress
        btnDockTest.setOnClickListener {
            simulateFieldIngress()
        }

        // SOS Distress Toggle
        btnDockSos.setOnClickListener {
            toggleEmergencyDistress()
        }
    }

    private fun updateModeUI() {
        if (isTxMode) {
            btnModeToggle.text = "MODE: TX"
            btnModeToggle.setTextColor(Color.parseColor("#E5A93C"))
            btnPtt3d.setImageResource(R.drawable.ic_ptt_mic)
            tvPttStatus.text = "HOLD TO TALK"
            tvPttStatus.setTextColor(Color.parseColor("#E5A93C"))
            tvModeHint.text = "Press and hold to broadcast offline voice note"
        } else {
            btnModeToggle.text = "MODE: RX"
            btnModeToggle.setTextColor(Color.parseColor("#00E676"))
            btnPtt3d.setImageResource(R.drawable.ic_speaker_wave)
            tvPttStatus.text = "LISTENING ON CH %02d".format(currentChannel)
            tvPttStatus.setTextColor(Color.parseColor("#00E676"))
            tvModeHint.text = "Monitoring mesh • Tap button to replay audio"
        }
    }

    private fun updateChannelDisplay() {
        val freq = channelFrequencies[currentChannel] ?: "433.750"
        tvChannelHeader.text = "CH %02d • %s MHz".format(currentChannel, freq)
        meshRouter.defaultChannel = currentChannel
        if (!isTxMode) {
            tvPttStatus.text = "LISTENING ON CH %02d".format(currentChannel)
        }
    }

    private fun showMacrosBottomSheet() {
        val dialog = BottomSheetDialog(this)
        val sheetView = layoutInflater.inflate(R.layout.sheet_tactical_macros, null)
        dialog.setContentView(sheetView)

        sheetView.findViewById<Button>(R.id.btn_sheet_medevac).setOnClickListener {
            broadcastMacro(TacticalMacro.MEDICAL_URGENT, "तत्काल चिकित्सा सहायता और एम्बुलेंस की आवश्यकता है")
            dialog.dismiss()
        }
        sheetView.findViewById<Button>(R.id.btn_sheet_fire).setOnClickListener {
            broadcastMacro(TacticalMacro.FIRE_RESCUE, "आग की आपात स्थिति • अग्निशमन दल तत्काल भेजें")
            dialog.dismiss()
        }
        sheetView.findViewById<Button>(R.id.btn_sheet_flood).setOnClickListener {
            broadcastMacro(TacticalMacro.FLOOD_EVACUATION, "जलस्तर बढ़ रहा है • तत्काल निकासी आवश्यक है")
            dialog.dismiss()
        }
        sheetView.findViewById<Button>(R.id.btn_sheet_ambush).setOnClickListener {
            broadcastMacro(TacticalMacro.SEARCH_RESCUE, "हमले की स्थिति • तत्काल बैकअप और कवर प्रदान करें")
            dialog.dismiss()
        }

        dialog.show()
    }

    private fun broadcastMacro(macro: TacticalMacro, text: String) {
        lifecycleScope.launch(Dispatchers.IO) {
            meshRouter.sendTacticalMacro(macro, channel = currentChannel, language = IndicLanguage.HINDI)
            withContext(Dispatchers.Main) {
                tvMsgHeader.text = "BROADCASTED MACRO (CH %02d)".format(currentChannel)
                tvMsgText.text = text
                tvMsgTelemetry.text = "6 Bytes • 99.96% Saved • 210 ms"
            }
        }
    }

    private fun simulateFieldIngress() {
        val sampleText = "गश्त दल सुरक्षित है • सेक्टर 4 में कोई हलचल नहीं"
        tvMsgHeader.text = "INGRESS FROM ALPHA-01 (CH %02d • HINDI)".format(currentChannel)
        tvMsgText.text = sampleText
        tvMsgTelemetry.text = "18 Bytes • 99.92% Saved • 380 ms"

        lifecycleScope.launch(Dispatchers.IO) {
            val audioSamples = nativeTts.synthesize(sampleText, speed = 1.0f)
            if (audioSamples.isNotEmpty()) {
                lastReceivedAudio = audioSamples
                audioPlayer.play(audioSamples)
            }
        }
    }

    private fun replayLastAudio() {
        lastReceivedAudio?.let { audio ->
            lifecycleScope.launch(Dispatchers.IO) {
                audioPlayer.play(audio)
            }
        }
    }

    private fun toggleEmergencyDistress() {
        isEmergencyDistressActive = !isEmergencyDistressActive
        if (isEmergencyDistressActive) {
            btnDockSos.text = "🚨 ACTIVE"
            btnDockSos.setBackgroundColor(Color.parseColor("#E53935"))
            tvMsgHeader.text = "🚨 EMERGENCY DISTRESS BROADCAST"
            tvMsgText.text = "अत्यंत आपातकालीन स्थिति • तत्काल सहायता भेजें"
            tvMsgTelemetry.text = "12 Bytes • HIGH PRIORITY • OVERRIDE"
            lifecycleScope.launch(Dispatchers.IO) {
                alertManager.triggerDistressAlert("अत्यंत आपातकालीन स्थिति", nativeTts, audioPlayer)
            }
        } else {
            btnDockSos.text = "🚨 SOS"
            btnDockSos.setBackgroundResource(R.drawable.bg_chip_callsign)
            alertManager.cancelAlarm()
        }
    }

    private fun onPttDown() {
        recordedAudioChunks.clear()
        audioRecorder.start(lifecycleScope) { chunk ->
            synchronized(recordedAudioChunks) {
                recordedAudioChunks.add(chunk)
            }
        }
    }

    private fun onPttUp() {
        audioRecorder.stop()
        lifecycleScope.launch(Dispatchers.IO) {
            val chunksCopy = synchronized(recordedAudioChunks) { recordedAudioChunks.toList() }
            if (chunksCopy.isEmpty()) return@launch

            val totalSize = chunksCopy.sumOf { it.size }
            val flatAudio = FloatArray(totalSize)
            var offset = 0
            for (chunk in chunksCopy) {
                System.arraycopy(chunk, 0, flatAudio, offset, chunk.size)
                offset += chunk.size
            }

            val recognizedText = nativeStt.transcribe(flatAudio)
            if (recognizedText.isNotBlank()) {
                meshRouter.sendVoiceNote(
                    text = recognizedText,
                    channel = currentChannel,
                    language = IndicLanguage.HINDI
                )
                withContext(Dispatchers.Main) {
                    tvMsgHeader.text = "BROADCASTED (CH %02d • YOU)".format(currentChannel)
                    tvMsgText.text = recognizedText
                    tvMsgTelemetry.text = "%d Bytes • 99.94%% Saved • 480 ms".format(recognizedText.toByteArray().size + 4)
                }
            }
        }
    }

    private fun startMeshReceiver() {
        meshRouter.startListening(lifecycleScope) { packet, sourceIp ->
            handleIncomingPacket(packet, sourceIp)
        }

        p2pTransport.startServer(lifecycleScope) { message ->
            if (message is P2PTransport.Message.Text) {
                lifecycleScope.launch(Dispatchers.Main) {
                    tvMsgHeader.text = "P2P INGRESS FROM ${message.sender}"
                    tvMsgText.text = message.content
                    tvMsgTelemetry.text = "%d Bytes • 420 ms".format(message.content.toByteArray().size)
                }
            }
        }
    }

    private fun handleIncomingPacket(packet: MicroRadioPacket, sourceIp: String) {
        val text = packet.resolvedText
        if (text.isBlank()) return

        lifecycleScope.launch(Dispatchers.IO) {
            withContext(Dispatchers.Main) {
                tvMsgHeader.text = "INGRESS FROM $sourceIp (CH %02d)".format(packet.channel)
                tvMsgText.text = text
                tvMsgTelemetry.text = "%d Bytes • 99.96%% Saved • 540 ms".format(packet.pack().size)
            }

            if (packet.isEmergency) {
                alertManager.triggerDistressAlert("[EMERGENCY] $text", nativeTts, audioPlayer)
            } else {
                val samples = nativeTts.synthesize(text, speed = 1.0f)
                if (samples.isNotEmpty()) {
                    lastReceivedAudio = samples
                    audioPlayer.play(samples)
                }
            }
        }
    }

    private fun triggerHapticClick() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vibratorManager = getSystemService(VIBRATOR_MANAGER_SERVICE) as? VibratorManager
                vibratorManager?.defaultVibrator?.vibrate(
                    VibrationEffect.createPredefined(VibrationEffect.EFFECT_HEAVY_CLICK)
                )
            } else {
                val vibrator = getSystemService(VIBRATOR_SERVICE) as? Vibrator
                @Suppress("DEPRECATION")
                vibrator?.vibrate(35)
            }
        } catch (_: Exception) {}
    }

    private fun checkPermissions() {
        val permissions = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.ACCESS_WIFI_STATE,
            Manifest.permission.CHANGE_WIFI_STATE
        )
        val missing = permissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 101)
        }
    }

    private fun setupEngines() {
        lifecycleScope.launch(Dispatchers.IO) {
            val modelBase = getExternalFilesDir(null)?.absolutePath ?: filesDir.absolutePath
            nativeStt.init(
                encoderPath = "$modelBase/models/stt/encoder.int8.onnx",
                decoderPath = "$modelBase/models/stt/decoder.onnx",
                joinerPath = "$modelBase/models/stt/joiner.int8.onnx",
                tokensPath = "$modelBase/models/stt/tokens.txt",
                vadModelPath = "$modelBase/models/vad/silero_vad.onnx"
            )

            nativeTts.init(
                modelPath = "$modelBase/models/tts/en_US-lessac-low.onnx",
                tokensPath = "$modelBase/models/tts/tokens.txt",
                dataDirPath = "$modelBase/models/tts/espeak-ng-data"
            )
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        audioRecorder.close()
        audioPlayer.close()
        meshRouter.close()
        p2pTransport.close()
        nativeStt.close()
        nativeTts.close()
        alertManager.cancelAlarm()
    }
}
