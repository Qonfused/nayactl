## @file
# Copyright (c) 2026, Cory Bennett. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
##
"""LED command group."""

from __future__ import annotations

import click

from ..constants import (CAT_LED, LED_ADJUST_BRIGHTNESS, LED_OFF, LED_ON,
                         LED_SELECT_EFFECT, LED_SET_MAX_BRIGHTNESS)
from .context import TransportContext, pass_ctx


def register(cli: click.Group) -> None:
  """Register LED command group."""

  @click.group()
  def led() -> None:
    """LED control commands."""

  @led.command("on")
  @pass_ctx
  def led_on(tctx: TransportContext) -> None:
    """Turn LEDs on."""
    transport = tctx.transport
    dest = getattr(transport, "dest", 0x50)
    transport.send_command(dest, CAT_LED, LED_ON)
    click.echo("LEDs on")

  @led.command("off")
  @pass_ctx
  def led_off(tctx: TransportContext) -> None:
    """Turn LEDs off."""
    transport = tctx.transport
    dest = getattr(transport, "dest", 0x50)
    transport.send_command(dest, CAT_LED, LED_OFF)
    click.echo("LEDs off")

  @led.command("brightness")
  @click.argument("level", type=int)
  @pass_ctx
  def led_brightness(tctx: TransportContext, level: int) -> None:
    """Set LED brightness (0-255)."""
    transport = tctx.transport
    dest = getattr(transport, "dest", 0x50)
    transport.send_command(dest, CAT_LED, LED_ADJUST_BRIGHTNESS, bytes([level & 0xFF]))
    click.echo(f"Brightness set to {level}")

  @led.command("effect")
  @click.argument("effect_id", type=int)
  @pass_ctx
  def led_effect(tctx: TransportContext, effect_id: int) -> None:
    """Select LED effect by ID."""
    transport = tctx.transport
    dest = getattr(transport, "dest", 0x50)
    transport.send_command(dest, CAT_LED, LED_SELECT_EFFECT, bytes([effect_id & 0xFF]))
    click.echo(f"Effect set to {effect_id}")

  @led.command("max-brightness")
  @click.argument("level", type=click.IntRange(0, 100))
  @click.option("--target", type=int, default=0, show_default=True,
                help="LED target selector (first payload byte)")
  @click.option("--payload", default=None,
                help="Override the whole payload, as hex.")
  @pass_ctx
  def led_max_brightness(tctx: TransportContext, level: int, target: int,
                         payload) -> None:
    """Set the global LED max-brightness ceiling.

    A persistent device-side ceiling, separate from the per-key LED map and
    from `led brightness`. While it is 0 the board stays completely dark, yet
    every LED command still returns a normal ack -- so it presents as dead
    hardware. Module LEDs sit outside the gate, so lit modules alongside a
    dark board is the tell.

    Payload is [target, level]. See docs/cdc-protocol.md; every command in the
    0xED category takes a target byte first, taken from NayaCore's parameter
    list and emitted ahead of the command data.

    The MEANING of the target byte is not yet known -- 0..3 all ack, and in
    testing they did not behave identically. Note that acks do not confirm
    application: this family acknowledges malformed payloads too, so verify by
    looking at the board.
    """
    transport = tctx.transport
    dest = getattr(transport, "dest", 0x50)
    data = bytes.fromhex(payload) if payload else bytes([target & 0xFF, level])
    frames = transport.send_command(dest, CAT_LED, LED_SET_MAX_BRIGHTNESS, data)
    click.echo(f"Sent SET_LED_MAX_BRIGHTNESS payload {data.hex()}; "
               f"{len(frames)} ack frame(s)")
    click.echo("Note: acks do not confirm the value was applied - check the board.")

  cli.add_command(led)
