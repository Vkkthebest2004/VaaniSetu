package com.vaanisetu.core

import kotlinx.coroutines.*
import java.io.Closeable
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketException

/**
 * High-speed offline UDP Broadcast Mesh Router for Android.
 *
 * Transmits MicroRadioPackets (4-33 bytes) over local ad-hoc WiFi / hotspot networks
 * with zero internet, zero cellular infrastructure, and zero cloud APIs.
 * Supports channels 1 through 16 with channel filtering and emergency alert prioritization.
 */
class MeshRouter(
    val port: Int = 8989,
    var defaultChannel: Int = 7
) : Closeable {

    private var socket: DatagramSocket? = null
    private var listenJob: Job? = null

    @Volatile
    var isRunning: Boolean = false
        private set

    /**
     * Start listening for broadcast MicroRadioPackets.
     *
     * @param scope CoroutineScope for the background listener.
     * @param onPacketReceived Callback invoked whenever a valid packet arrives on our channel or as an emergency.
     */
    fun startListening(
        scope: CoroutineScope,
        onPacketReceived: (packet: MicroRadioPacket, sourceIp: String) -> Unit
    ) {
        if (isRunning) return

        try {
            socket = DatagramSocket(port).apply {
                broadcast = true
                reuseAddress = true
            }
            isRunning = true

            listenJob = scope.launch(Dispatchers.IO) {
                val buffer = ByteArray(512) // MicroRadio packets are < 64 bytes
                while (isActive && isRunning) {
                    try {
                        val datagram = DatagramPacket(buffer, buffer.size)
                        socket?.receive(datagram)

                        val rawData = datagram.data.copyOfRange(datagram.offset, datagram.offset + datagram.length)
                        val packet = MicroRadioPacket.unpack(rawData)

                        if (packet != null) {
                            // Accept packet if it matches our active channel OR if it is an emergency alert
                            if (packet.channel == defaultChannel || packet.isEmergency) {
                                withContext(Dispatchers.Main) {
                                    onPacketReceived(packet, datagram.address.hostAddress ?: "Unknown")
                                }
                            }
                        }
                    } catch (e: SocketException) {
                        if (!isRunning) break
                    } catch (e: Exception) {
                        // Log or ignore corrupted datagram
                    }
                }
            }
        } catch (e: Exception) {
            isRunning = false
        }
    }

    /**
     * Broadcast a MicroRadioPacket across the local network (255.255.255.255).
     */
    suspend fun broadcastPacket(packet: MicroRadioPacket): Boolean = withContext(Dispatchers.IO) {
        try {
            val rawBytes = packet.pack()
            val broadcastAddr = InetAddress.getByName("255.255.255.255")
            val datagram = DatagramPacket(rawBytes, rawBytes.size, broadcastAddr, port)

            val sock = socket ?: DatagramSocket().apply { broadcast = true }
            sock.send(datagram)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Broadcast a quick voice text message on the active channel.
     */
    suspend fun sendVoiceNote(
        text: String,
        channel: Int = defaultChannel,
        language: IndicLanguage = IndicLanguage.HINDI
    ): Boolean {
        val packet = MicroRadioPacket(
            text = text,
            channel = channel,
            language = language,
            packetType = PacketType.NORMAL_PTT
        )
        return broadcastPacket(packet)
    }

    /**
     * Broadcast a 4-byte tactical distress macro (Flood, Medical, Fire, etc.).
     */
    suspend fun sendTacticalMacro(
        macro: TacticalMacro,
        channel: Int = defaultChannel,
        language: IndicLanguage = IndicLanguage.HINDI
    ): Boolean {
        val packet = MicroRadioPacket(
            text = "",
            channel = channel,
            language = language,
            packetType = PacketType.TACTICAL_MACRO,
            macro = macro
        )
        return broadcastPacket(packet)
    }

    fun stop() {
        isRunning = false
        listenJob?.cancel()
        listenJob = null
        try {
            socket?.close()
        } catch (_: Exception) {}
        socket = null
    }

    override fun close() {
        stop()
    }
}
