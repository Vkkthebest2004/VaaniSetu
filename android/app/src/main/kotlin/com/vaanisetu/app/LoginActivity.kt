package com.vaanisetu.app

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

/**
 * Tactical Authentication and Operational Role Gateway.
 *
 * Provides operator verification with Tactical PIN credentials and dual-mode selection:
 * - SENDER MODE (TX): Field unit equipped with 3D Push-To-Talk microphone, tactical macros, and SOS beacon.
 * - RECEIVER MODE (RX): Command listening station monitoring channels, decoding MicroRadio packets, and synthesizing speech.
 */
class LoginActivity : AppCompatActivity() {

    private lateinit var cardModeSender: LinearLayout
    private lateinit var cardModeReceiver: LinearLayout
    private lateinit var rbModeSender: RadioButton
    private lateinit var rbModeReceiver: RadioButton
    private lateinit var tvTitleSender: TextView
    private lateinit var tvTitleReceiver: TextView

    private lateinit var chipCallsignAlpha: TextView
    private lateinit var chipCallsignHq: TextView
    private lateinit var chipCallsignEcho: TextView
    private lateinit var chipCallsignBravo: TextView

    private lateinit var etOperatorCallsign: EditText
    private lateinit var etTacticalPin: EditText
    private lateinit var btnQuickPin: Button
    private lateinit var tvAuthError: TextView
    private lateinit var btnAuthorizeConnect: Button

    private var selectedMode: String = "SENDER" // "SENDER" or "RECEIVER"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        bindViews()
        setupListeners()
        updateModeUI()
    }

    private fun bindViews() {
        cardModeSender = findViewById(R.id.card_mode_sender)
        cardModeReceiver = findViewById(R.id.card_mode_receiver)
        rbModeSender = findViewById(R.id.rb_mode_sender)
        rbModeReceiver = findViewById(R.id.rb_mode_receiver)
        tvTitleSender = findViewById(R.id.tv_title_sender)
        tvTitleReceiver = findViewById(R.id.tv_title_receiver)

        chipCallsignAlpha = findViewById(R.id.chip_callsign_alpha)
        chipCallsignHq = findViewById(R.id.chip_callsign_hq)
        chipCallsignEcho = findViewById(R.id.chip_callsign_echo)
        chipCallsignBravo = findViewById(R.id.chip_callsign_bravo)

        etOperatorCallsign = findViewById(R.id.et_operator_callsign)
        etTacticalPin = findViewById(R.id.et_tactical_pin)
        btnQuickPin = findViewById(R.id.btn_quick_pin)
        tvAuthError = findViewById(R.id.tv_auth_error)
        btnAuthorizeConnect = findViewById(R.id.btn_authorize_connect)
    }

    private fun setupListeners() {
        // Mode Selection
        cardModeSender.setOnClickListener {
            selectedMode = "SENDER"
            updateModeUI()
        }

        cardModeReceiver.setOnClickListener {
            selectedMode = "RECEIVER"
            updateModeUI()
        }

        // Preset Callsign Chips
        chipCallsignAlpha.setOnClickListener {
            selectCallsignChip(chipCallsignAlpha, "ALPHA-01")
        }
        chipCallsignHq.setOnClickListener {
            selectCallsignChip(chipCallsignHq, "COMMAND-HQ")
            // Automatically recommend Receiver mode for Command HQ
            selectedMode = "RECEIVER"
            updateModeUI()
        }
        chipCallsignEcho.setOnClickListener {
            selectCallsignChip(chipCallsignEcho, "ECHO-07")
        }
        chipCallsignBravo.setOnClickListener {
            selectCallsignChip(chipCallsignBravo, "BRAVO-02")
        }

        // Auto-fill PIN
        btnQuickPin.setOnClickListener {
            etTacticalPin.setText("1947")
            tvAuthError.text = "Tactical security clearance authorized."
            tvAuthError.setTextColor(Color.parseColor("#00E676"))
        }

        // Authorize Action
        btnAuthorizeConnect.setOnClickListener {
            val pin = etTacticalPin.text.toString().trim()
            if (pin.isEmpty()) {
                tvAuthError.text = "Error: Enter tactical PIN (Default: 1947)."
                tvAuthError.setTextColor(Color.parseColor("#FF5252"))
                return@setOnClickListener
            }

            var callsign = etOperatorCallsign.text.toString().trim()
            if (callsign.isEmpty()) {
                callsign = if (selectedMode == "SENDER") "ALPHA-01" else "COMMAND-HQ"
            }

            if (selectedMode == "SENDER") {
                val intent = Intent(this, WalkieTalkieActivity::class.java).apply {
                    putExtra(EXTRA_OPERATOR_CALLSIGN, callsign)
                    putExtra(EXTRA_MODE, "SENDER")
                }
                startActivity(intent)
            } else {
                val intent = Intent(this, ReceiverActivity::class.java).apply {
                    putExtra(EXTRA_OPERATOR_CALLSIGN, callsign)
                    putExtra(EXTRA_MODE, "RECEIVER")
                }
                startActivity(intent)
            }
        }
    }

    private fun selectCallsignChip(selectedChip: TextView, callsign: String) {
        val allChips = listOf(chipCallsignAlpha, chipCallsignHq, chipCallsignEcho, chipCallsignBravo)
        for (chip in allChips) {
            if (chip == selectedChip) {
                chip.setBackgroundResource(R.drawable.bg_chip_callsign_active)
                chip.setTextColor(Color.parseColor("#E5A93C"))
            } else {
                chip.setBackgroundResource(R.drawable.bg_chip_callsign)
                chip.setTextColor(Color.parseColor("#A0A5B5"))
            }
        }
        etOperatorCallsign.setText(callsign)
    }

    private fun updateModeUI() {
        if (selectedMode == "SENDER") {
            cardModeSender.setBackgroundResource(R.drawable.bg_mode_card_selected)
            cardModeReceiver.setBackgroundResource(R.drawable.bg_mode_card_unselected)
            rbModeSender.isChecked = true
            rbModeReceiver.isChecked = false
            tvTitleSender.setTextColor(Color.parseColor("#FFFFFF"))
            tvTitleReceiver.setTextColor(Color.parseColor("#9E9E9E"))
            btnAuthorizeConnect.text = "AUTHORIZE & LOAD SENDER (TX)"
        } else {
            cardModeSender.setBackgroundResource(R.drawable.bg_mode_card_unselected)
            cardModeReceiver.setBackgroundResource(R.drawable.bg_mode_card_selected)
            rbModeSender.isChecked = false
            rbModeReceiver.isChecked = true
            tvTitleSender.setTextColor(Color.parseColor("#9E9E9E"))
            tvTitleReceiver.setTextColor(Color.parseColor("#00E676"))
            btnAuthorizeConnect.text = "AUTHORIZE & LOAD RECEIVER (RX)"
        }
    }

    companion object {
        const val EXTRA_OPERATOR_CALLSIGN = "extra_operator_callsign"
        const val EXTRA_MODE = "extra_mode"
    }
}
