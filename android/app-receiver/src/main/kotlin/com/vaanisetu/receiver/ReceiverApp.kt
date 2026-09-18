package com.vaanisetu.receiver

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.util.Log
import java.io.File
import java.io.FileOutputStream

class ReceiverApp : Application() {

    companion object {
        private const val TAG = "ReceiverApp"
        const val NOTIFICATION_CHANNEL_ID = "vaanisetu_receiver_channel"

        lateinit var modelBasePath: String
            private set
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        modelBasePath = (getExternalFilesDir(null) ?: filesDir).absolutePath
        extractModelsIfNeeded()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.notification_channel_desc)
                setShowBadge(false)
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun extractModelsIfNeeded() {
        val versionFile = File(modelBasePath, "models/.version")
        val currentVersion = "1.0.0"

        if (versionFile.exists() && versionFile.readText().trim() == currentVersion) {
            Log.d(TAG, "Models already extracted (v$currentVersion), skipping.")
            return
        }

        try {
            extractAssetDir("models")
            versionFile.parentFile?.mkdirs()
            versionFile.writeText(currentVersion)
            Log.d(TAG, "Model extraction complete.")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to extract models: ${e.message}", e)
        }
    }

    private fun extractAssetDir(assetPath: String) {
        val assetManager = assets
        val files = assetManager.list(assetPath) ?: return

        if (files.isEmpty()) {
            val outFile = File(modelBasePath, assetPath)
            outFile.parentFile?.mkdirs()
            assetManager.open(assetPath).use { input ->
                FileOutputStream(outFile).use { output ->
                    input.copyTo(output, bufferSize = 8192)
                }
            }
        } else {
            for (file in files) {
                extractAssetDir("$assetPath/$file")
            }
        }
    }
}
