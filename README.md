# cipfried

Tibia process automation and passive network tooling for Linux.

cipfried hooks the Tibia client process, extracts the session XTEA key from its
memory, captures Tibia traffic with Scapy, and decodes the encrypted packet
stream. It does not inject traffic and does not require a proxy.

## Requirements

- Linux
- Python 3.10 or newer
- Tibia installed locally
- Permission to inspect the Tibia process and capture network traffic

Reading process memory is controlled by the kernel `ptrace` policy. Capturing
packets normally requires root or the appropriate capabilities.

## Install

```bash
make install
```

This creates `.venv` and installs the project with its development dependencies.

## Run

```bash
sudo -E .venv/bin/python -m cipfried.main
```

Or with `make`:

```bash
sudo -E make run
```

The sniffer starts before the Tibia process is hooked, so it can capture the
login traffic needed to discover the session key. Start cipfried, then start
Tibia and log in.

The default stop hotkey is `p`.

## Logging

Set `CIPFRIED_LOG_LEVEL` to change verbosity:

```bash
sudo -E CIPFRIED_LOG_LEVEL=DEBUG .venv/bin/python -m cipfried.main
```

INFO logs show lifecycle events, key changes, and endpoint selection. DEBUG logs
include frame-level details; payload hex is only emitted at DEBUG level.

## Development

```bash
make lint
make typecheck
make test
make check
```

See [docs/network.md](docs/network.md) for the packet pipeline and design notes.

## Troubleshooting

- `Cannot access process ... memory`: check the kernel `ptrace_scope` setting and
  run with sufficient privileges.
- `Unable to start Tibia capture`: verify the network interface and capture
  permissions.
- No packets decoded: confirm the client is logged in and the key watcher has
  reported a loaded key. Try `CIPFRIED_LOG_LEVEL=DEBUG`.
