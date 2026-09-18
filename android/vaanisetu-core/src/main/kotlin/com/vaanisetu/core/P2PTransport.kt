package com.vaanisetu.core

import kotlinx.coroutines.*
import java.io.*
import java.net.ServerSocket
import java.net.Socket

/**
 * Offline Peer-to-Peer Transport for VaaniSetu.
 *
 * Transmits voice messages and text over local WiFi Direct sockets
 * or Bluetooth with 100% offline, zero-cloud, zero-cell-tower operation.
 */
class P2PTransport(
    private val port: Int = 8988
) : Closeable {

    private var serverSocket: ServerSocket? = null
    private var serverJob: Job? = null
    @Volatile
    var isRunning: Boolean = false
        private set

    sealed class Message {
        data class Text(val content: String, val sender: String) : Message()
        data class Audio(val pcmData: ByteArray, val sampleRate: Int, val sender: String) : Message()
    }

    /**
     * Start listening for incoming P2P connections on local WiFi mesh/hotspot.
     */
    fun startServer(scope: CoroutineScope, onMessageReceived: (Message) -> Unit) {
        if (isRunning) return

        try {
            serverSocket = ServerSocket().apply {
                reuseAddress = true
                bind(java.net.InetSocketAddress(port))
            }
            isRunning = true
        } catch (e: Exception) {
            isRunning = false
            return
        }

        serverJob = scope.launch(Dispatchers.IO) {
            while (isActive && isRunning) {
                try {
                    val client = serverSocket?.accept() ?: break
                    launch {
                        handleClient(client, onMessageReceived)
                    }
                } catch (e: Exception) {
                    if (!isRunning) break
                }
            }
        }
    }

    private fun handleClient(client: Socket, onMessageReceived: (Message) -> Unit) {
        client.use { sock ->
            val dis = DataInputStream(BufferedInputStream(sock.getInputStream()))
            val type = dis.readByte().toInt()
            val sender = dis.readUTF()

            when (type) {
                1 -> { // Text message
                    val text = dis.readUTF()
                    onMessageReceived(Message.Text(text, sender))
                }
                2 -> { // Audio packet
                    val sampleRate = dis.readInt()
                    val length = dis.readInt()
                    val pcm = ByteArray(length)
                    dis.readFully(pcm)
                    onMessageReceived(Message.Audio(pcm, sampleRate, sender))
                }
            }
        }
    }

    /**
     * Send a text message to a peer IP address directly.
     */
    suspend fun sendText(peerIp: String, text: String, sender: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                Socket(peerIp, port).use { sock ->
                    val dos = DataOutputStream(BufferedOutputStream(sock.getOutputStream()))
                    dos.writeByte(1) // type: text
                    dos.writeUTF(sender)
                    dos.writeUTF(text)
                    dos.flush()
                }
                true
            } catch (e: Exception) {
                false
            }
        }

    /**
     * Send raw PCM audio to a peer IP address directly.
     */
    suspend fun sendAudio(peerIp: String, pcmData: ByteArray, sampleRate: Int = 16000, sender: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                Socket(peerIp, port).use { sock ->
                    val dos = DataOutputStream(BufferedOutputStream(sock.getOutputStream()))
                    dos.writeByte(2) // type: audio
                    dos.writeUTF(sender)
                    dos.writeInt(sampleRate)
                    dos.writeInt(pcmData.size)
                    dos.write(pcmData)
                    dos.flush()
                }
                true
            } catch (e: Exception) {
                false
            }
        }

    fun stop() {
        isRunning = false
        serverJob?.cancel()
        serverJob = null
        try {
            serverSocket?.close()
        } catch (e: Exception) {
            // Ignore
        }
        serverSocket = null
    }

    override fun close() {
        stop()
    }
}
