from dataclasses import dataclass
from typing import Final

DEFAULT_SERVER_PORT: Final[int] = 7171
DEFAULT_KEY_POLL_INTERVAL: Final[float] = 5.0
DEFAULT_PACKET_QUEUE_SIZE: Final[int] = 2000
DEFAULT_ACTIVE_TIMEOUT: Final[float] = 10.0
DEFAULT_SERVER_CONFIRM_PACKETS: Final[int] = 2
DEFAULT_MAX_PENDING_PACKETS: Final[int] = 256
DEFAULT_RESCAN_INTERVAL: Final[float] = 30.0


@dataclass(frozen=True)
class Settings:
    server_port: int = DEFAULT_SERVER_PORT
    key_poll_interval: float = DEFAULT_KEY_POLL_INTERVAL
    packet_queue_size: int = DEFAULT_PACKET_QUEUE_SIZE
    active_timeout: float = DEFAULT_ACTIVE_TIMEOUT
    server_confirm_packets: int = DEFAULT_SERVER_CONFIRM_PACKETS
    max_pending_packets: int = DEFAULT_MAX_PENDING_PACKETS
    rescan_interval: float = DEFAULT_RESCAN_INTERVAL


__all__ = [
    "DEFAULT_ACTIVE_TIMEOUT",
    "DEFAULT_KEY_POLL_INTERVAL",
    "DEFAULT_MAX_PENDING_PACKETS",
    "DEFAULT_PACKET_QUEUE_SIZE",
    "DEFAULT_RESCAN_INTERVAL",
    "DEFAULT_SERVER_CONFIRM_PACKETS",
    "DEFAULT_SERVER_PORT",
    "Settings",
]
