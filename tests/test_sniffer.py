import pytest

import cipfried.network.sniffer as sniffer_module
from cipfried.network.sniffer import TibiaSniffer
from cipfried.network.xtea import XteaCipher
from tests.helpers import (
    CLIENT_IP,
    CLIENT_PORT,
    OTHER_SERVER_IP,
    SERVER_IP,
    SERVER_PORT,
    make_frame,
    make_tcp_packet,
)


def server_packet(
    cipher: XteaCipher,
    first_sequence: int,
    payloads: list[bytes],
    *,
    source_ip: str = SERVER_IP,
    sequence: int = 1,
) -> object:
    data = b"".join(
        make_frame(cipher, first_sequence + offset, payload)
        for offset, payload in enumerate(payloads)
    )
    return make_tcp_packet(
        data,
        from_client=False,
        sequence=sequence,
        source_ip=source_ip,
        destination_ip=CLIENT_IP,
        source_port=SERVER_PORT,
        destination_port=CLIENT_PORT,
    )


def test_selects_first_confirmed_server_endpoint(cipher: XteaCipher) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)
    sniffer.set_cipher(cipher)

    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))
    sniffer._handle_packet(server_packet(cipher, 10, [b"other"], source_ip=OTHER_SERVER_IP))

    assert [packet.payload for packet in packets] == [b"one", b"two"]
    assert sniffer._active_server == (SERVER_IP, SERVER_PORT)


def test_buffers_until_cipher_and_replays(cipher: XteaCipher) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)

    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))
    assert packets == []

    sniffer.set_cipher(cipher)

    assert [packet.payload for packet in packets] == [b"one", b"two"]


def test_replayed_packets_mark_endpoint_as_fresh(cipher: XteaCipher) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)

    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))
    sniffer.set_cipher(cipher)
    assert sniffer._active_server == (SERVER_IP, SERVER_PORT)

    sniffer._handle_packet(server_packet(cipher, 10, [b"other", b"server"], source_ip=OTHER_SERVER_IP))

    assert sniffer._active_server == (SERVER_IP, SERVER_PORT)


def test_buffers_initial_packets_until_endpoint_is_confirmed(cipher: XteaCipher) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)
    sniffer.set_cipher(cipher)
    first = make_frame(cipher, 1, b"one")
    second = make_frame(cipher, 2, b"two")

    sniffer._handle_packet(
        make_tcp_packet(
            first,
            from_client=False,
            sequence=1,
            source_ip=SERVER_IP,
            destination_ip=CLIENT_IP,
            source_port=SERVER_PORT,
            destination_port=CLIENT_PORT,
        )
    )
    assert packets == []

    sniffer._handle_packet(
        make_tcp_packet(
            second,
            from_client=False,
            sequence=1 + len(first),
            source_ip=SERVER_IP,
            destination_ip=CLIENT_IP,
            source_port=SERVER_PORT,
            destination_port=CLIENT_PORT,
        )
    )

    assert [packet.payload for packet in packets] == [b"one", b"two"]


def test_switches_from_stale_endpoint(cipher: XteaCipher, monkeypatch: pytest.MonkeyPatch) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)
    sniffer.set_cipher(cipher)

    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))
    other_data = make_frame(cipher, 10, b"other") + make_frame(cipher, 11, b"server")
    sniffer._handle_packet(
        make_tcp_packet(
            other_data,
            from_client=False,
            sequence=1,
            source_ip=OTHER_SERVER_IP,
            destination_ip=CLIENT_IP,
            source_port=SERVER_PORT,
            destination_port=CLIENT_PORT,
        )
    )
    assert len(packets) == 2

    monkeypatch.setattr(sniffer_module, "ACTIVE_TIMEOUT", -1.0)
    switched_data = make_frame(cipher, 12, b"switched")
    sniffer._handle_packet(
        make_tcp_packet(
            switched_data,
            from_client=False,
            sequence=1 + len(other_data),
            source_ip=OTHER_SERVER_IP,
            destination_ip=CLIENT_IP,
            source_port=SERVER_PORT,
            destination_port=CLIENT_PORT,
        )
    )

    assert sniffer._active_server == (OTHER_SERVER_IP, SERVER_PORT)
    assert packets[-1].payload == b"switched"


def test_key_change_clears_active_endpoint(cipher: XteaCipher, other_cipher: XteaCipher) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)
    sniffer.set_cipher(cipher)
    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))

    assert sniffer._active_server is not None

    sniffer.set_cipher(other_cipher)

    assert sniffer._active_server is None


def test_fin_clears_active_endpoint(cipher: XteaCipher) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)
    sniffer.set_cipher(cipher)
    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))
    assert sniffer._active_server is not None

    sniffer._handle_packet(
        make_tcp_packet(
            b"",
            from_client=False,
            source_ip=SERVER_IP,
            destination_ip=CLIENT_IP,
            source_port=SERVER_PORT,
            destination_port=CLIENT_PORT,
            flags="FA",
        )
    )

    assert sniffer._active_server is None


def test_syn_resets_stream(cipher: XteaCipher) -> None:
    packets = []
    sniffer = TibiaSniffer(packets.append)
    sniffer.set_cipher(cipher)
    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))
    assert sniffer._active_server is not None

    sniffer._handle_packet(
        make_tcp_packet(
            b"",
            from_client=False,
            source_ip=SERVER_IP,
            destination_ip=CLIENT_IP,
            source_port=SERVER_PORT,
            destination_port=CLIENT_PORT,
            flags="S",
        )
    )

    assert sniffer._active_server is None


def test_validates_cipher_against_buffered_server_frames(
    cipher: XteaCipher, other_cipher: XteaCipher
) -> None:
    sniffer = TibiaSniffer()
    sniffer._handle_packet(server_packet(cipher, 1, [b"one", b"two"]))

    assert sniffer.validate_cipher(cipher)
    assert not sniffer.validate_cipher(other_cipher)


def test_start_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncSniffer:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            self.start_count = 0
            self.stop_count = 0

        def start(self) -> None:
            self.start_count += 1

        def stop(self) -> None:
            self.stop_count += 1

    monkeypatch.setattr(sniffer_module, "AsyncSniffer", FakeAsyncSniffer)
    sniffer = TibiaSniffer()

    sniffer.start()
    sniffer.start()

    assert sniffer.is_running
    fake = sniffer._sniffer
    assert isinstance(fake, FakeAsyncSniffer)
    assert fake.start_count == 1

    sniffer.stop()
    assert fake.stop_count == 1
    assert not sniffer.is_running


def test_start_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingSniffer:
        def __init__(self, **kwargs: object) -> None:
            pass

        def start(self) -> None:
            raise OSError("no permission")

    monkeypatch.setattr(sniffer_module, "AsyncSniffer", FailingSniffer)

    with pytest.raises(RuntimeError, match="Unable to start Tibia capture"):
        TibiaSniffer().start()
