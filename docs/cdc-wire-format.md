# Naya Create CDC Binary Protocol — Wire Format

Reconstructed from NayaCore.exe reverse-engineering (v1.19.1).

## Message Structure

Each binary CDC message is serialized as follows (from `FUN_1403207e0`):

```
Byte  Struct Offset  Field
────  ─────────────  ─────────────────────────────
 0    0x30           destination (0x50=left, 0x51=right)
 1    0x31           source? / flags?
 2    0x32           unknown
 3    0x33           unknown
 4    0x34           category (0x30=remap, 0xBE=ble, 0xDE=module, 0xED=led, 0xEE=reset, 0xFA=flash, 0xFE=system, 0xFF=meta)
 5    0x35           unknown
 6    0x37 (!!)      subcmd HIGH byte  ← NOTE: bytes 6 and 7 are SWAPPED vs struct layout
 7    0x36 (!!)      subcmd LOW byte   ← subcmd is big-endian on wire, read as LE short at 0x36
 8    0x38           parameter count or flags
 [9..N]  0x40+       payload data (variable length, may be empty)
 N+1  0x58           trailer byte (status/checksum?)
 N+2  (literal)      0x04 = EOT terminator (always appended)
```

## Key Observations

- Subcmd bytes are **byte-swapped** between struct and wire: struct offset 0x37 is written first, then 0x36
- This means the subcmd `0x1008` (TOGGLE_KEYSCAN_MODE) would appear as bytes `10 08` on the wire
- Message always ends with `0x04` (EOT character)
- The struct field at offset 0x36 is read as a `short` for dispatch (e.g., `0x1008`, `0x1009`)

## Destination Addresses

From `_getDestination` (`FUN_1402bd2c0`):
- Device type 1 (CreateLeft) → `0x50`
- Device type 2 (CreateRight) → `0x51`  
- Device type 3 (Dongle) → `0x50`

## System Commands (category 0xFE)

| SubCmd | Name                    | Payload                                              |
|--------|-------------------------|------------------------------------------------------|
| 0x1001 | MEDIA ID REQUEST        | —                                                    |
| 0x1002 | GET FW VERSION          | —                                                    |
| 0x1003 | MODULE BATTERY RECOVERY | —                                                    |
| 0x1004 | GET HW ID NUMBER        | —                                                    |
| 0x1005 | SET HOST OS             | 1 byte                                               |
| 0x1006 | GET KB BATTERY LEVEL    | —                                                    |
| 0x1007 | SET RELEASE MODE        | 1 byte                                               |
| 0x1008 | TOGGLE KEYSCAN MODE     | 1 byte (mode value)                                  |
| 0x1009 | KEYSCAN EVENT           | 3 bytes (response only, routed to IntegrationWorker) |

## TOGGLE_KEYSCAN_MODE Validation

From error strings:
- "Invalid parameter size (%1) for TOGGLE_KEYSCAN_MODE, should be 1" → exactly 1 byte payload
- "Empty parameter for TOGGLE_KEYSCAN_MODE" → payload must not be empty
- "Invalid keyscan_mode (%1) for TOGGLE_KEYSCAN_MODE, should be %2 or %3" → two valid values

The two valid values are compared against constants (likely 0 and 1, or 1 and 2).

## KEYSCAN_EVENT Response

From `_handleKeyscanEvent` (`FUN_140264070`):
- Exactly 3 bytes expected in payload (offset 0x40 in message struct)
- `byte[0]` at payload[0], `byte[1]` at payload[1], `byte[2]` at payload[2]
- Emitted via Qt signal: `QMetaObject::activate(param_1, &metaObject, 0, {byte0, byte1, byte2})`
- In `_handleMessage`, only command `0x1009` is routed here; all others are "Unknown/Unimplemented"

## Inbound Message Routing

Messages from the keyboard are dispatched based on category byte:
- Category `0xFE` → `_handleSysResponse` (which delegates by subcmd)
  - Subcmd `0x1009` (KEYSCAN_EVENT) → **explicitly rejected** ("should not be routed here")
  - Other subcmds → normal response handling
- The IntegrationWorker receives messages where subcmd == `0x1009` via a separate dispatch path
- This means KEYSCAN_EVENT bypasses the normal command/response flow

## Serial Port Configuration (for reference)

- VID: 0x37D1
- PID Left: 0x0064, PID Right: 0x00C8, PID Dongle: 0x012C
- Baud: 115200
- Data: 8 bits, No parity, 1 stop bit
- Flow: DTR + RTS enabled

## Text Commands (separate from binary protocol)

The keyboard also accepts ASCII text commands terminated with `\r\n`:
- `fwvchk\r\n`
- `keyboard_mode_release_toggle\r\n`
- `ble_Address\r\n`
- `dump_settings\r\n`
- etc.

These appear to be processed by a different handler on the keyboard (SystemCDC vs ProtocolCDC).
