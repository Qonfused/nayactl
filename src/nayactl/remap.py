## @file
# Copyright (c) 2026, Cory Bennett. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
##
"""Remap category (0x30): layer, macro, module-config and LED-map access.

The LED map is the per-key colour table the firmware uses to light the board.
It became firmware-side in NayaFlow v1.25.0 ("Enabled LED remapping on FW
side"); before that the keyboard lit itself from built-in effects only.

Entry format (4 bytes, reverse-engineered against FW 3.41.0 and verified
against a known palette on real hardware):

    [position, hue_lo, hue_hi, value]

    position    0..59, index into the half's LED position table
    hue         uint16 little-endian, in DEGREES (0..360)
    value       0..100 brightness; 0 means that key is dark

This matches naya_remap::LED(int position, unsigned short hue,
unsigned char value) exactly. Saturation is not part of the map.

Note the hue is genuinely 16-bit: the palette runs past 255 degrees, so
reading byte[2] as its own field silently turns violet into a brightness
of zero.

A per-key value of 100 does NOT guarantee light. The device also holds a
global LED max-brightness (LED category 0xED, subcmd 0x1013); when that is
0 the whole board stays dark regardless of this map, of any effect, and of
LED_ADJUST_BRIGHTNESS. Check it before concluding the map is at fault.

Every entry carries its own position, so the table is self-addressing.

Only reads are implemented here. WRITE_LED_MAP is listed for completeness
but is deliberately not exposed: on FW 3.41.0 a standalone write is
acknowledged and then silently discarded, and an oversized one is not
rejected at all -- it wedges the CDC frame parser until the keyboard is
power-cycled. NayaFlow drives this write as one step of a larger
WRITE_PROFILE sequence, so the preceding steps are probably required.
Anyone implementing it should expect power cycles.
"""

from __future__ import annotations

from typing import NamedTuple

CAT_REMAP = 0x30

REMAP_READ_LAYER_LIST         = 0x1001
REMAP_WRITE_LAYER_LIST        = 0x1002
REMAP_READ_LAYER_DATA         = 0x1003
REMAP_WRITE_LAYER_DATA        = 0x1004
REMAP_READ_MACRO_LIST         = 0x1005
REMAP_WRITE_MACRO_LIST        = 0x1006
REMAP_READ_MACRO_DATA         = 0x1007
REMAP_WRITE_MACRO_DATA        = 0x1008
REMAP_READ_MODULE_CONFIG_LIST = 0x1009
REMAP_WRITE_MODULE_CONFIG_LIST= 0x100A
REMAP_READ_MODULE_CONFIG_DATA = 0x100B
REMAP_WRITE_MODULE_CONFIG_DATA= 0x100C
REMAP_READ_LED_MAP            = 0x100D
REMAP_WRITE_LED_MAP           = 0x100E
REMAP_CLEAR_ALL_DATA          = 0x10CA

REMAP_NAMES = {
  REMAP_READ_LAYER_LIST:          "READ_LAYER_LIST",
  REMAP_WRITE_LAYER_LIST:         "WRITE_LAYER_LIST",
  REMAP_READ_LAYER_DATA:          "READ_LAYER_DATA",
  REMAP_WRITE_LAYER_DATA:         "WRITE_LAYER_DATA",
  REMAP_READ_MACRO_LIST:          "READ_MACRO_LIST",
  REMAP_WRITE_MACRO_LIST:         "WRITE_MACRO_LIST",
  REMAP_READ_MACRO_DATA:          "READ_MACRO_DATA",
  REMAP_WRITE_MACRO_DATA:         "WRITE_MACRO_DATA",
  REMAP_READ_MODULE_CONFIG_LIST:  "READ_MODULE_CONFIG_LIST",
  REMAP_WRITE_MODULE_CONFIG_LIST: "WRITE_MODULE_CONFIG_LIST",
  REMAP_READ_MODULE_CONFIG_DATA:  "READ_MODULE_CONFIG_DATA",
  REMAP_WRITE_MODULE_CONFIG_DATA: "WRITE_MODULE_CONFIG_DATA",
  REMAP_READ_LED_MAP:             "READ_LED_MAP",
  REMAP_WRITE_LED_MAP:            "WRITE_LED_MAP",
  REMAP_CLEAR_ALL_DATA:           "CLEAR_ALL_DATA",
}

ENTRY_SIZE = 4
LEDS_PER_HALF = 60

MAX_VALUE = 100


class LedEntry(NamedTuple):
  """One key's colour in the firmware LED map."""

  position: int
  hue: int      #: degrees, 0..360
  value: int    #: brightness, 0..100

  def to_bytes(self) -> bytes:
    return bytes([
      self.position & 0xFF,
      self.hue & 0xFF,
      (self.hue >> 8) & 0xFF,
      self.value & 0xFF,
    ])

  @property
  def is_dark(self) -> bool:
    """True when this key renders no light, whatever its hue."""
    return self.value == 0


class RemapError(Exception):
  pass


def parse_led_map(frame: bytes) -> tuple[int, list[LedEntry]]:
  """Parse a READ_LED_MAP reply frame into (layer, entries).

  Frame layout: header(6) + [subcmd_hi, subcmd_lo, flags, layer] + entries
  + checksum(1) + EOT(1).
  """
  if len(frame) < 12:
    raise RemapError(f"LED map frame too short: {len(frame)} bytes")
  body = frame[6:-2]
  if len(body) < 4:
    raise RemapError("LED map frame has no payload")
  layer = body[3]
  raw = body[4:]
  usable = len(raw) // ENTRY_SIZE * ENTRY_SIZE
  entries = [
    LedEntry(
      position=raw[i],
      hue=raw[i + 1] | (raw[i + 2] << 8),
      value=raw[i + 3],
    )
    for i in range(0, usable, ENTRY_SIZE)
  ]
  return layer, entries


def summarise(entries: list[LedEntry]) -> str:
  """One-line description of an LED map, for CLI output."""
  if not entries:
    return "empty"
  dark = sum(1 for e in entries if e.is_dark)
  hues = sorted({e.hue for e in entries})
  vals = sorted({e.value for e in entries})
  return (
    f"{len(entries)} entries, {dark} dark; "
    f"value={vals} hues(deg)={hues[:8]}"
  )
