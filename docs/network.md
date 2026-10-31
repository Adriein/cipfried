# Network pipeline

cipfried captures Tibia's TCP traffic and decodes the encrypted game protocol
without acting as a proxy.

## High-level flow

```text
Tibia client
    │
    │ TCP 7171
    ▼
Scapy capture ──► TCP reassembly ──► frame parser ──► XTEA decrypt
                                                         │
                                                         ▼
                                                  padding removal
                                                         │
                                                         ▼
                                             raw DEFLATE (optional)
                                                         │
                                                         ▼
                                                   TibiaPacket
```

## TCP reassembly

`cipfried.network.reassembly.TcpReassembler` orders segments by TCP sequence
number before passing bytes to the protocol decoder. It supports out-of-order
segments, duplicates, overlaps, and 32-bit sequence wraparound.

If a gap never arrives and the pending buffer grows too large, the reassembler
advances to the oldest pending segment instead of stalling forever. The skipped
bytes are logged as a warning.

## Packet framing

Each Tibia frame starts with an unencrypted six-byte header:

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 2 | XTEA block count, little-endian |
| 2 | 2 | Tibia sequence number, little-endian |
| 4 | 2 | Compression flag, little-endian |

The payload is `block_count * 8` bytes. Valid compression flags are `0x0000`
(uncompressed) and `0xC000` (raw DEFLATE).

The total frame size is:

```text
6 + block_count * 8
```

## XTEA decryption and padding

The payload is encrypted with XTEA in ECB mode using 32 cycles. After
decryption, the first byte is the number of padding bytes at the end of the
payload. The padding byte is removed along with the padding itself.

A padding byte greater than 7 indicates an invalid frame. The decoder then
resynchronizes on the next plausible frame boundary.

## DEFLATE decompression

Compressed frames use raw DEFLATE (`wbits=-15`). The stream is stateful per
connection direction, so each direction owns a separate decompressor.

Tibia strips the four-byte `Z_SYNC_FLUSH` marker (`00 00 ff ff`) from each
compressed frame; the receiver appends it again before decompressing. If zlib
reports an error, the decompressor resets and retries the frame once. A failed
frame is dropped without dropping the rest of the stream.

## Synchronization

When a cipher is installed, the decoder buffers bytes until it finds two
consecutive frames with valid headers and padding. Requiring two frames reduces
false positives from random padding bytes.

Before the XTEA key is known, the decoder keeps raw bytes in a bounded buffer.
When the key becomes available, the buffered bytes are replayed through the
normal frame parser.

## Key extraction

The Tibia session key is found in process memory:

1. Scan for the 16-byte anchor `ffffffffffffff3f0400000000000000`.
2. Two anchors appear 160 bytes apart.
3. The 16-byte key is 24 bytes before the second anchor.

The key can change after a new login. cipfried polls process memory, caches
anchor addresses, and validates candidate keys against frames already captured
from the server before replacing the active key.

## Endpoint selection

Tibia connections can resolve to multiple endpoints; only one carries the real
game session. cipfried decodes all server streams but dispatches packets from a
single active endpoint. Endpoint health is tracked using decoded packets, frame
failures, and last activity. If the active endpoint goes silent, cipfried can
switch to another endpoint that is decoding successfully.

## Why not mitmproxy?

A proxy can control the connection from the start and can inject traffic, but it
changes how the client connects and requires routing Tibia through it. cipfried
uses passive capture so it can run alongside an unmodified client. Proxy-based
tools remain useful when traffic injection is required.
