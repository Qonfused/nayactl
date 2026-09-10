# Naya Create CDC Protocol - Command Reference

Reconstructed from NayaCore.exe reverse-engineering (v1.19.1).

The protocol uses a 3-byte header: `[category, subcmd_hi, subcmd_lo]` where category selects the command group and subcmd is a 16-bit command ID.

## Message Categories

| Byte | Category |
|------|----------|
| 0x30 | Remap (Layer/Macro/Module Config/LED Map) |
| 0xBE | BLE (Bluetooth Low Energy) |
| 0xCA | Unknown |
| 0xDE | Module |
| 0xED | LED |
| 0xEE | Reset |
| 0xF1 | Unknown |
| 0xFA | SPI Flash |
| 0xFE | System |
| 0xFF | Meta / Compound |

## 0x30 — Remap Commands

| SubCmd | Name |
|--------|------|
| 0x1001 | READ LAYER LIST |
| 0x1002 | WRITE LAYER LIST |
| 0x1003 | READ LAYER DATA |
| 0x1004 | WRITE LAYER DATA |
| 0x1005 | READ MACRO LIST |
| 0x1006 | WRITE MACRO LIST |
| 0x1007 | READ MACRO DATA |
| 0x1008 | WRITE MACRO DATA |
| 0x1009 | READ MODULE CONFIG LIST |
| 0x100A | WRITE MODULE CONFIG LIST |
| 0x100B | READ MODULE CONFIG DATA |
| 0x100C | WRITE MODULE CONFIG DATA |
| 0x100D | READ LED MAP DATA |
| 0x100E | WRITE LED MAP DATA |
| 0x10CA | CLEAR ALL DATA |

## 0xBE — BLE Commands

| SubCmd | Name |
|--------|------|
| 0x1001 | SET PAIR ADDRESS |
| 0x1002 | GET PAIR ADDRESS |
| 0x1003 | UNPAIR PAIR ADDRESS |
| 0x1004 | UNPAIR ALL PAIRS |
| 0x1005 | GET ALL PAIRS |
| 0x1006 | GET BLE NAME |
| 0x1007 | SET BLE NAME |
| 0x1008 | GET BLE ADDRESS |
| 0x1009 | SELECT BLE PROFILE |
| 0x100A | CLEAR BLE PROFILE |
| 0x100B | SELECT BLE OUT |
| 0x100C | GET BLE STATUS |
| 0x100D | GET DONGLE ADDR |
| 0x100E | GET SLOTX ADDR |
| 0x100F | GET BLE FW VERSION |
| 0x1010 | CLEAR ALL SPLIT LINKS |

## 0xDE — Module Commands

| SubCmd | Name |
|--------|------|
| 0x1001 | SEND HANDSHAKE |
| 0x1002 | MODULE DETECT |
| 0x1003 | CHECK HANDSHAKE |
| 0x1005 | MODULE FWUP |
| 0x1006 | RESET MODULE |
| 0x1007 | GET ADDRESS |
| 0x1008 | GET MODULE FW VERSION |
| 0x1009 | GET BATTERY |
| 0x100A | MODULE FILE FW VERSION |
| 0x100B | GET PRECISE BATTERY LEVEL |

## 0xED — LED Commands

| SubCmd | Name |
|--------|------|
| 0x1003 | LEDs ON |
| 0x1004 | LEDs OFF |
| 0x1005 | TOGGLE LEDs |
| 0x1006 | LEDs INCREMENT |
| 0x1007 | LEDs DECREMENT |
| 0x1008 | LED ADJUST BRIGHTNESS |
| 0x1009 | LEDs RED |
| 0x100A | LEDs GREEN |
| 0x100B | LEDs BLUE |
| 0x100C | LEDs WHITE |
| 0x100D | LEDs EFFECT CYCLE |
| 0x100E | LEDs HUE SATURATION |
| 0x100F | LEDs HALT |
| 0x1010 | LEDs RESUME |
| 0x1011 | SELECT LEDs EFFECT |
| 0x1050 | LEDs RGB BRIGHTNESS |
| 0x10D1 | FORCE LEDs ON |
| 0x10D2 | FORCE LEDs OFF |

## 0xEE — Reset Commands

| SubCmd | Name |
|--------|------|
| 0x10AE | MCU BOOT RESET |
| 0x10BE | DFU RESET |
| 0x10CE | NORMAL RESET |

## 0xFA — SPI Flash Commands

| SubCmd | Name |
|--------|------|
| 0x1001 | TEST FLASH |
| 0x1002 | FORMAT PARTITION |
| 0x1006 | ERASE CHIP |

## 0xFE — System Commands

| SubCmd | Name |
|--------|------|
| 0x1001 | MEDIA ID REQUEST |
| 0x1002 | GET FW VERSION |
| 0x1003 | MODULE BATTERY RECOVERY |
| 0x1004 | GET HW ID NUMBER |
| 0x1005 | SET HOST OS |
| 0x1006 | GET KB BATTERY LEVEL |
| 0x1007 | SET RELEASE MODE |
| 0x1008 | **TOGGLE KEYSCAN MODE** |
| 0x1009 | **KEYSCAN EVENT** |

## 0xFF — Meta / Compound Commands

| SubCmd | Name |
|--------|------|
| 0x1000 | WAIT |
| 0x1001 | VERIFY FLASH |
| 0x1002 | ENQUEUE READ LAYERS |
| 0x1003 | GET MODULE INFO IF PRESENT |

## Keyscan Event Flow

1. Host sends `TOGGLE_KEYSCAN_MODE` (0xFE/0x1008) with 1 byte parameter to enable/disable
2. Device sends `KEYSCAN_EVENT` (0xFE/0x1009) messages — 3 bytes of data
3. Integration worker `_handleKeyscanEvent` receives 3-byte payload
4. The 3 bytes are: `[byte0, byte1, byte2]` — emitted via Qt signal `QMetaObject::activate`
5. Signal is broadcast to `si_keyscanEvent_brc_source`

## Integration Worker Message Routing

The `_handleMessage` function checks the subcmd field at offset 0x36 in the message struct:
- `0x1009` → `_handleKeyscanEvent` (the only command routed to integration worker)
- Everything else → "Unknown/Unimplemented command received. Dropping packet"

## Serial Commands (Text-based, CRLF-terminated)

These are sent over the CDC serial port as ASCII:
- `fwvchk\r\n` — check firmware version
- `ble_Address\r\n` — get BLE MAC
- `ble_Pair#<addr>\r\n` — pair BLE
- `keyboard_mode_release_toggle\r\n` — toggle keyboard mode
- `manual_fw_update_touch\r\n` — force touch module FW update
- `manual_fw_update_track\r\n` — force track module FW update
- `manual_fw_update_tune\r\n` — force tune module FW update
- `mcuboot_reset` — enter MCUboot
- `clear_bonds` — clear all BLE bonds
- `dump_settings` — dump device settings
- `force_touch_start` — force touch module start

## 0xED — LED Command Payloads

Reconstructed from `ProtocolCDCProcessWorker::_constructLEDMessages` in
NayaCore v6.11.0 (macOS build, unstripped).

Every command in this category takes a **target byte first**. NayaCore appends
`params[0][0]` to a "static payload", appends the command-specific data to a
"dynamic payload", and the message queue concatenates the two — so the wire
payload is `[target] + [data...]`.

| Command | Params | Wire payload | Range checks |
|---------|--------|--------------|--------------|
| `LEDS_ON` / `OFF` / `TOGGLE` / `HALT` / `RESUME` / `EFFECT_CYCLE` | 1 | `[target]` | — |
| `LEDS_INC` / `LEDS_DEC` | 2 | `[target, amount]` | amount < 101 |
| `LED_ADJ_BRT` | 2 | `[target, brightness]` | brightness 0..100 |
| `SEL_LEDS_EFF` | 2 | `[target, effect_id]` | effect_id < count |
| `LEDS_HUE_SAT` | 4 | `[target, hue_lo, hue_hi, sat]` | hue < 361, sat < 101 |
| `LEDS_RGB_BRT` | 5 | `[target, p1, p2, p3, brightness]` | brightness < 101 |

Out-of-range values are **clamped to 100 with a warning, not rejected**, so a
bad value still produces a valid-looking message.

The meaning of the target byte is not yet established.

Two traps worth knowing:

- **Acks do not confirm application.** A well-formed frame carrying nonsense
  parameters returns the same ack as a valid one. An ack proves the frame
  parsed, nothing more. Verify LED changes by looking at the board.
- **A missing target is rejected host-side**, not on the wire: sending a
  command with an empty payload trips "Missing or empty target parameter for
  LED command" inside NayaCore, so the firmware never sees it.

Payloads are chunked at 242 bytes, with a hard limit of 257.
