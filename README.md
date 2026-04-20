# nayactl

Command-line toolkit for interacting with the Naya Create split keyboard over USB CDC.

`nayactl` supports both high-level text commands and low-level binary CDC commands, with helpers for device discovery, status inspection, BLE/module introspection, LED control, keyscan streaming, and raw protocol commands.

## Features

- Discover connected Naya Create devices (`scan`)
- Inspect keyboard + module status (`status`)
- Query BLE address, pair list, and BLE status (`ble`)
- Control LEDs (`led`)
- Stream keyscan events (`keyscan`)
- Listen to inbound CDC traffic (`listen`)
- Send text commands used by device firmware (`text`)
- Send raw binary CDC category/subcommand payloads (`raw`)

## Requirements

- Python 3.10+
- Linux/macOS/Windows with serial access (serial path)
- Naya Create device connected over USB

## Installation

### Option A: local editable install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then run:

```bash
nayactl --help
```

### Option B: launcher script

This repository includes local launcher scripts at project root:

```bash
./nayactl --help
```

```bat
nayactl.cmd --help
```

Notes:
- `./nayactl` is POSIX shell (Linux/macOS).
- `nayactl.cmd` is for Windows `cmd.exe`.
- The Python entrypoint also works cross-platform (`nayactl` after install, or `python -m nayactl`).

## Quick Start

```bash
# Discover connected halves/dongles
./nayactl scan

# Show status for all discovered devices
./nayactl status

# Target a specific side
./nayactl --side left status

# BLE helpers
./nayactl ble address
./nayactl ble pairs
./nayactl ble status

# Send a text command
./nayactl text dump_settings

# Run keyscan for 10 seconds
./nayactl keyscan -d 10
```

## Example: status output

```bash
$ sudo ./nayactl status
Create Left:
	Firmware:    3.30.1
	HW ID:       53••••••••••••37
	BLE Address: CE:67:••:••:••:98
	Battery:     97%
	Voltage:     4.173V
	Module:      Touch
		FW:        2.2.2
		Battery:   98%
		Voltage:   4.1895V
		USB/Qi:    4.5756V
		Charging:  USB
```

Output can vary by side/module and whether external charging is present.

## Command Reference

Top-level options:

- `-p, --port TEXT` — serial port (auto-detected if omitted)
- `--side [left|right|dongle]` — target a specific half/dongle
- `--force` — allow dangerous commands
- `-v, --verbose` — verbose output

Top-level commands:

- `scan` — scan for connected Naya devices
- `status` — show keyboard/module status for connected halves
- `ble` — Bluetooth commands (`address`, `pairs`, `status`)
- `module` — module commands (`info`, `battery`, `status`)
- `led` — LED commands (`on`, `off`, `brightness`, `effect`)
- `keyscan` — enable keyscan mode and stream key events
- `listen` — passive CDC frame listener
- `text` — send firmware text command
- `raw` — send raw binary CDC command

For per-command details:

```bash
./nayactl <command> --help
```

Examples:

```bash
./nayactl text --help
./nayactl ble --help
./nayactl raw --help
```

## Protocol Notes

This repo includes reverse-engineered protocol references:

- `docs/cdc-protocol.md` — category/subcommand reference
- `docs/cdc-wire-format.md` — binary wire layout and routing notes

In code:

- `src/nayactl/protocol.py` — frame building/parsing
- `src/nayactl/constants.py` — command/category IDs
- `src/nayactl/bluetooth.py` — BLE response parsing helpers

## Development

Run in editable mode and invoke via module:

```bash
python -m nayactl --help
```

Repository layout:

- `src/nayactl/cli/` — CLI command modules
- `src/nayactl/transport.py` — serial transport + safety checks
- `src/nayactl/discovery.py` — port discovery
- `src/nayactl/protocol.py` — CDC message format handling

## Safety

Some firmware actions are intentionally gated as dangerous.

Use `--force` only when you explicitly intend to run commands that can change device state beyond normal querying/control.

## License

This project is licensed under the [Apache-2.0 License](LICENSE).

## Troubleshooting

- If no device appears, run `./nayactl scan` and verify cable/data mode.
- On Linux, serial permissions may require adding your user to `dialout` (or running with elevated permissions).
- Use `-v` to inspect raw command/response bytes while debugging.

## Platform Notes

- The primary CLI serial workflow (`scan`, `status`, `ble`, `module`, `led`, `keyscan`, `listen`, `text`, `raw`) is built on `pyserial` and `serial.tools.list_ports`, which are cross-platform.
- Linux is currently the most directly exercised path in this repository.
- Linux-specific code paths only affect optional/discovery helpers for ZMQ and NayaCore internals (`/proc`, `/dev/shm`, `/tmp` probing) and are not used by the main serial CLI commands.
