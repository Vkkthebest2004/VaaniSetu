"""
Offline Bluetooth Transceiver for Direct Phone-to-Phone Pairing.
Uses RFCOMM / L2CAP serial sockets to exchange iTantra neural packets
with zero WiFi or network infrastructure.
"""

import socket
import threading
from typing import Callable, Optional
from .protocol import RadioPacket


class BluetoothTransceiver:
    """
    Bluetooth point-to-point transceiver.
    Transmits lightweight neural radio packets between paired phones.
    """

    DEFAULT_CHANNEL = 4

    def __init__(self, channel: int = 4):
        self.channel = channel
        self.running = False
        self._server_sock: Optional[socket.socket] = None
        self._client_sock: Optional[socket.socket] = None
        self._callback: Optional[Callable[[RadioPacket, str], None]] = None

    def start_listener(self, on_packet_received: Callable[[RadioPacket, str], None]):
        """Listen for incoming Bluetooth connections."""
        self._callback = on_packet_received
        self.running = True

        # Check if Bluetooth socket family is supported on this OS
        bt_family = getattr(socket, "AF_BLUETOOTH", None)
        bt_proto = getattr(socket, "BTPROTO_RFCOMM", None)

        if bt_family and bt_proto:
            try:
                self._server_sock = socket.socket(bt_family, socket.SOCK_STREAM, bt_proto)
                self._server_sock.bind(("", self.channel))
                self._server_sock.listen(1)
                threading.Thread(target=self._accept_loop, daemon=True).start()
                return
            except Exception as e:
                pass

        # Fallback to local TCP simulation socket for desktop testing
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("127.0.0.1", 9200 + self.channel))
        self._server_sock.listen(1)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running and self._server_sock:
            try:
                client, addr = self._server_sock.accept()
                threading.Thread(target=self._client_read_loop, args=(client, str(addr)), daemon=True).start()
            except Exception:
                if not self.running:
                    break

    def _client_read_loop(self, sock: socket.socket, addr_str: str):
        with sock:
            while self.running:
                try:
                    data = sock.recv(2048)
                    if not data:
                        break
                    pkt = RadioPacket.deserialize(data)
                    if pkt and self._callback:
                        self._callback(pkt, addr_str)
                except Exception:
                    break

    def send_packet_to_device(self, target_address: str, packet: RadioPacket) -> bool:
        """Send packet to a remote Bluetooth device."""
        data = packet.serialize()
        bt_family = getattr(socket, "AF_BLUETOOTH", None)
        bt_proto = getattr(socket, "BTPROTO_RFCOMM", None)

        if bt_family and bt_proto:
            try:
                sock = socket.socket(bt_family, socket.SOCK_STREAM, bt_proto)
                sock.connect((target_address, self.channel))
                sock.sendall(data)
                sock.close()
                return True
            except Exception:
                pass

        # Fallback simulation
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", 9200 + self.channel))
            sock.sendall(data)
            sock.close()
            return True
        except Exception:
            return False

    def stop(self):
        self.running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
