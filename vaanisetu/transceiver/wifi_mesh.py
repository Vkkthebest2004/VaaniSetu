"""
Offline WiFi Mesh & UDP Broadcast Transceiver for Walkie-Talkie Channels.
Enables instant 1-to-many communication across local WiFi Direct or Hotspot links
without internet, routers, or cell towers.
"""

import socket
import threading
import time
from typing import Callable, Optional
from .protocol import RadioPacket


class WiFiMeshTransceiver:
    """
    Broadcasts and receives iTantra binary radio packets on local WiFi mesh.
    Channels (1-16) map to UDP broadcast ports or multicast groups.
    """

    BASE_PORT = 9100

    def __init__(self, channel: int = 1, broadcast_ip: str = "255.255.255.255"):
        self.channel = max(1, min(16, channel))
        self.broadcast_ip = broadcast_ip
        self.port = self.BASE_PORT + self.channel
        self.running = False
        self._sock: Optional[socket.socket] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[RadioPacket, str], None]] = None

    def start(self, on_packet_received: Callable[[RadioPacket, str], None]):
        """Start listening on the current channel."""
        self._callback = on_packet_received
        self.running = True

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            # Bind to all interfaces on channel port
            self._sock.bind(("", self.port))
        except Exception as e:
            # If already bound, fall back to localhost
            self._sock.bind(("127.0.0.1", self.port))

        self._recv_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._recv_thread.start()

    def _listen_loop(self):
        while self.running and self._sock:
            try:
                data, addr = self._sock.recvfrom(2048)
                packet = RadioPacket.deserialize(data)
                if packet and self._callback:
                    self._callback(packet, addr[0])
            except Exception:
                if not self.running:
                    break

    def send_packet(self, packet: RadioPacket) -> bool:
        """Broadcast packet to all listeners on this channel."""
        if not self._sock:
            return False

        data = packet.serialize()
        try:
            # Send to broadcast IP
            self._sock.sendto(data, (self.broadcast_ip, self.port))
            # Also send to loopback for local testing
            self._sock.sendto(data, ("127.0.0.1", self.port))
            return True
        except Exception as e:
            # Fallback to loopback
            try:
                self._sock.sendto(data, ("127.0.0.1", self.port))
                return True
            except Exception:
                return False

    def change_channel(self, new_channel: int):
        """Switch to a new channel (1-16)."""
        cb = self._callback
        self.stop()
        self.channel = max(1, min(16, new_channel))
        self.port = self.BASE_PORT + self.channel
        if cb:
            self.start(cb)

    def stop(self):
        """Stop listening."""
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
