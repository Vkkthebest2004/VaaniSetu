package com.vaanisetu.sender

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.animation.AnimationUtils
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Tactical Starting / Booting Animation for VaaniSetu Sender App.
 */
@SuppressLint("CustomSplashScreen")
class SenderSplashActivity : AppCompatActivity() {

    private var hasNavigated = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash)

        val rootLayout = findViewById<View>(R.id.layout_splash_root)
        val outerRing = findViewById<View>(R.id.view_radar_ring_outer)
        val innerRing = findViewById<View>(R.id.view_radar_ring_inner)
        val logo = findViewById<ImageView>(R.id.iv_splash_logo)
        val tvTicker = findViewById<TextView>(R.id.tv_splash_ticker)

        // Start animations
        val animOuter = AnimationUtils.loadAnimation(this, R.anim.anim_radar_expand)
        val animInner = AnimationUtils.loadAnimation(this, R.anim.anim_radar_expand)
        val animLogo = AnimationUtils.loadAnimation(this, R.anim.anim_pulse_glow)

        animOuter.startOffset = 400
        outerRing?.startAnimation(animOuter)
        innerRing?.startAnimation(animInner)
        logo?.startAnimation(animLogo)

        // Ticker sequence & transition
        lifecycleScope.launch {
            delay(500)
            tvTicker?.text = "SCANNING 433 MHz MESH FREQUENCIES..."
            delay(600)
            tvTicker?.text = "CH 08 LOCKED [433.750 MHz] • SENDER TX READY"
            delay(700)
            navigateToMain()
        }

        // Tap to skip
        rootLayout?.setOnClickListener {
            navigateToMain()
        }
    }

    private fun navigateToMain() {
        if (hasNavigated) return
        hasNavigated = true

        val intent = Intent(this, SenderActivity::class.java)
        startActivity(intent)
        overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
        finish()
    }
}
