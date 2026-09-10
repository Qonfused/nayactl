## @file
# Copyright (c) 2026, Cory Bennett. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
##
"""Remap command group: LED map inspection."""

from __future__ import annotations

import json
import time

import click

from ..constants import DEST_LEFT, DEST_RIGHT
from ..remap import CAT_REMAP, REMAP_READ_LED_MAP, parse_led_map, summarise
from .context import TransportContext, pass_ctx

LAYERS = (0, 1, 2)
SIDES = {"left": DEST_LEFT, "right": DEST_RIGHT}


def _read_map(transport, dest: int, layer: int):
  """Read one layer's LED map. Returns (entries, raw_hex) or (None, None)."""
  frames = transport.send_command(
    dest, CAT_REMAP, REMAP_READ_LED_MAP, bytes([layer]), timeout=2.5
  )
  if not frames:
    return None, None
  raw = frames[0].raw
  _, entries = parse_led_map(raw)
  return entries, raw.hex()


def register(cli: click.Group) -> None:
  """Register the remap command group."""

  @click.group()
  def remap() -> None:
    """Layer, macro and LED-map (category 0x30) commands."""

  @remap.command("read-led-map")
  @click.option("--layer", type=int, default=None, help="Layer (default: all)")
  @click.option("--side", type=click.Choice(list(SIDES)), default="left",
                show_default=True)
  @click.option("--raw", is_flag=True, help="Also print raw frame hex")
  @pass_ctx
  def read_led_map(tctx: TransportContext, layer, side, raw) -> None:
    """Read the firmware per-key LED map.

    Only the primary (left) half answers this; the right half is driven over
    the split link and returns nothing, which is expected and harmless.
    """
    transport = tctx.transport
    dest = SIDES[side]
    for lyr in (LAYERS if layer is None else (layer,)):
      entries, hexstr = _read_map(transport, dest, lyr)
      if entries is None:
        click.echo(f"layer {lyr}: no reply")
        continue
      click.echo(f"layer {lyr}: {summarise(entries)}")
      if raw:
        click.echo(f"  {hexstr}")
      time.sleep(0.3)

  @remap.command("backup-led-map")
  @click.argument("path", type=click.Path(dir_okay=False))
  @click.option("--side", type=click.Choice(list(SIDES)), default="left",
                show_default=True)
  @pass_ctx
  def backup_led_map(tctx: TransportContext, path, side) -> None:
    """Save every layer's LED map to a JSON file as raw frames."""
    transport = tctx.transport
    dest = SIDES[side]
    out = {}
    for lyr in LAYERS:
      entries, hexstr = _read_map(transport, dest, lyr)
      if entries is None:
        click.echo(f"layer {lyr}: no reply, skipped")
        continue
      out[str(lyr)] = hexstr
      click.echo(f"layer {lyr}: {summarise(entries)}")
      time.sleep(0.3)
    if not out:
      raise click.ClickException("nothing read; refusing to write an empty backup")
    with open(path, "w") as fh:
      json.dump(out, fh, indent=2)
    click.echo(f"\nsaved {len(out)} layer(s) to {path}")

  cli.add_command(remap)
