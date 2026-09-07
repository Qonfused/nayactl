## @file
# Copyright (c) 2026, Cory Bennett. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
##
"""Status command."""

from __future__ import annotations

import click

from ..constants import (
  BLE_GET_ADDRESS,
  CAT_BLE,
  CAT_MODULE,
  CAT_SYSTEM,
  MOD_DETECT,
  MOD_GET_BATTERY,
  MOD_GET_FW_VERSION,
  MOD_GET_PRECISE_BATTERY,
  MOD_SEND_HANDSHAKE,
  MOD_GET_ADDRESS,
  module_type_from_address,
  module_side_from_address,
  SYS_GET_FW_VERSION,
  SYS_GET_HW_ID_NUMBER,
  SYS_GET_KB_BATTERY_LEVEL,
)
from ..discovery import find_naya_serial_ports
from ..transport import Transport, TransportError
from ..util import format_fw_version, hexline
from .context import TransportContext, pass_ctx
from .responses import first_payload


# Module voltages are carried internally in units of 0.1 mV (so 42000 == 4.2 V), which is what
# MODULE_GET_BATTERY reports natively. MODULE_GET_PRECISE_BATTERY reports plain millivolts instead:
# sent back to back to the same module, it answers 0x1038 (4152) while MODULE_GET_BATTERY answers
# 0xA1CF (41423). The old code fed the precise value straight into the 0.1 mV maths, rendering a
# full module as 0.41 V / 1%.
#
# The precise value is sniffed rather than blindly multiplied by 10: no real cell reads below
# 1.0 V, so anything under 10000 is unambiguously millivolts. That keeps the fix a no op if an
# older module firmware turns out to report the precise value in 0.1 mV already.
MODULE_VOLTAGE_MV_LIMIT = 10000


def _precise_voltage_to_tenth_mv(raw: int) -> int:
  """Convert a MODULE_GET_PRECISE_BATTERY reading (mV) to the internal 0.1 mV unit."""
  return raw * 10 if 0 < raw < MODULE_VOLTAGE_MV_LIMIT else raw


def _module_battery_percent(voltage: int) -> int:
  """Map a 0.1 mV cell voltage onto 1-100% over the 3.3 V - 4.2 V window."""
  clamped = max(33000, min(42000, voltage))
  return max(1, min(100, ((clamped - 33000) * 100) // 9000))


def _query_half(transport: Transport, dest: int, verbose: bool = False) -> dict:
  """Query a single keyboard half for its status and module info."""
  info: dict = {}

  payload = first_payload(transport.send_command(dest, CAT_SYSTEM, SYS_GET_FW_VERSION))
  if payload is not None:
    info["fw_version"] = format_fw_version(payload)
    if verbose:
      click.echo(f"  [raw] GET_FW_VERSION: {hexline(payload)}")

  payload = first_payload(transport.send_command(dest, CAT_SYSTEM, SYS_GET_HW_ID_NUMBER))
  if payload is not None:
    try:
      info["hw_id"] = payload.decode("ascii")
    except (UnicodeDecodeError, ValueError):
      info["hw_id"] = hexline(payload)

  kb_voltages = []
  for _ in range(5):
    payload = first_payload(
      transport.send_command(dest, CAT_SYSTEM, SYS_GET_KB_BATTERY_LEVEL, timeout=0.5),
    )
    if payload is not None and len(payload) >= 2:
      kb_voltages.append((payload[0] << 8) | payload[1])

  if kb_voltages:
    kb_voltages.sort()
    millivolts = kb_voltages[len(kb_voltages) // 2]
    clamped = max(3300, min(4200, millivolts))
    info["battery"] = max(1, min(100, ((clamped - 3300) * 100) // 900))
    info["kb_voltage"] = millivolts
    if verbose:
      click.echo(
        f"  [raw] GET_KB_BATTERY_LEVEL: voltages={kb_voltages} "
        f"median={millivolts} mV → {info['battery']}%",
      )

  payload = first_payload(transport.send_command(dest, CAT_BLE, BLE_GET_ADDRESS))
  if payload is not None and len(payload) >= 6:
    info["ble_addr"] = ":".join(f"{b:02X}" for b in payload[:6])
    if verbose:
      click.echo(f"  [raw] BLE_GET_ADDRESS: {hexline(payload)}")

  handshake = first_payload(
    transport.send_command(dest, CAT_MODULE, MOD_SEND_HANDSHAKE, timeout=1.5))
  if verbose and handshake is not None:
    click.echo(f"  [raw] MODULE_HANDSHAKE: {hexline(handshake)}")
  payload = first_payload(transport.send_command(dest, CAT_MODULE, MOD_DETECT))
  if verbose and payload is not None:
    click.echo(f"  [raw] MODULE_DETECT: {hexline(payload)}")

  if payload is not None and len(payload) >= 1 and payload[0] != 0:
    module_info: dict = {}
    # MODULE_DETECT's payload is presence, not type -- the handshake reply carries the
    # dock-bus address as [01][addr]; fall back to GET_ADDRESS if it did not answer.
    addr = None
    if (handshake is not None and len(handshake) >= 2 and
        handshake[0] == 0x01):
      addr = handshake[1]
    if addr is None:
      addr_payload = first_payload(transport.send_command(dest, CAT_MODULE, MOD_GET_ADDRESS))
      if verbose and addr_payload is not None:
        click.echo(f"  [raw] MODULE_GET_ADDRESS: {hexline(addr_payload)}")
      if addr_payload is not None and len(addr_payload) >= 1:
        addr = addr_payload[0]
    module_info["type"] = module_type_from_address(addr)
    if addr is not None:
      module_info["address"] = f"0x{addr:02X}"
      module_info["docked"] = module_side_from_address(addr)

    module_payload = first_payload(transport.send_command(dest, CAT_MODULE, MOD_GET_FW_VERSION))
    if module_payload is not None:
      module_info["fw_version"] = format_fw_version(module_payload)
      if verbose:
        click.echo(f"  [raw] MODULE_FW_VERSION: {hexline(module_payload)}")

    module_payload = first_payload(transport.send_command(dest, CAT_MODULE, MOD_GET_PRECISE_BATTERY))
    if module_payload is not None and len(module_payload) >= 2:
      if verbose:
        click.echo(f"  [raw] MODULE_PRECISE_BATTERY: {hexline(module_payload)}")
      voltage = _precise_voltage_to_tenth_mv((module_payload[0] << 8) | module_payload[1])
      valid = (module_payload[2] == 0) if len(module_payload) >= 3 else True
      if valid and voltage > 0:
        module_info["voltage"] = voltage
        module_info["battery"] = _module_battery_percent(voltage)

    if "battery" not in module_info:
      batt_voltages = []
      usb_voltages = []
      for _ in range(5):
        module_payload = first_payload(
          transport.send_command(dest, CAT_MODULE, MOD_GET_BATTERY, timeout=0.5),
        )
        if module_payload is not None and len(module_payload) >= 3:
          batt_voltages.append((module_payload[1] << 8) | module_payload[2])
          if len(module_payload) >= 5:
            usb_voltages.append((module_payload[3] << 8) | module_payload[4])
      if batt_voltages:
        batt_voltages.sort()
        raw_voltage = batt_voltages[len(batt_voltages) // 2]
        if raw_voltage > 0:
          module_info["battery"] = _module_battery_percent(raw_voltage)
          module_info["voltage"] = raw_voltage
        if verbose:
          click.echo(
            f"  [raw] MODULE_GET_BATTERY: voltages={batt_voltages} "
            f"median={raw_voltage}",
          )
      if usb_voltages:
        usb_voltages.sort()
        usb_voltage = usb_voltages[len(usb_voltages) // 2]
        if usb_voltage > 0:
          module_info["usb_voltage"] = usb_voltage
          if usb_voltage > 4000:
            module_info["charging_source"] = "Qi" if usb_voltage < 45000 else "USB"

    info["module"] = module_info

  return info


def _print_half_status(label: str, info: dict) -> None:
  """Pretty-print the status of one keyboard half."""
  click.echo(f"{label}:")
  if "fw_version" in info:
    click.echo(f"  Firmware:    {info['fw_version']}")
  if "hw_id" in info:
    click.echo(f"  HW ID:       {info['hw_id']}")
  if "ble_addr" in info:
    click.echo(f"  BLE Address: {info['ble_addr']}")
  if "battery" in info:
    click.echo(f"  Battery:     {info['battery']}%")
  if "kb_voltage" in info:
    millivolts = info["kb_voltage"]
    click.echo(f"  Voltage:     {millivolts / 1000:.3f}V")

  module_info = info.get("module")
  if module_info:
    click.echo(f"  Module:      {module_info.get('type', 'Unknown')}")
    if "address" in module_info:
      docked = module_info.get("docked")
      side = f"  ({docked} half)" if docked else ""
      click.echo(f"    Address:   {module_info['address']}{side}")
    if "fw_version" in module_info:
      click.echo(f"    Firmware:  {module_info['fw_version']}")
    if "battery" in module_info:
      click.echo(f"    Battery:   {module_info['battery']}%")
    if "voltage" in module_info:
      voltage = module_info["voltage"]
      click.echo(f"    Voltage:   {voltage / 10000:.4f}V")
    if "usb_voltage" in module_info:
      usb_voltage = module_info["usb_voltage"]
      click.echo(f"    USB/Qi:    {usb_voltage / 10000:.4f}V")
    if "charging_source" in module_info:
      click.echo(f"    Charging:  {module_info['charging_source']}")
    if "battery" not in module_info:
      click.echo("    Battery:   unknown")
  else:
    click.echo("  Module:      None")


def register(cli: click.Group) -> None:
  """Register status command."""

  @cli.command()
  @pass_ctx
  def status(tctx: TransportContext) -> None:
    """Show device status for all connected halves and modules."""
    if tctx.port:
      transport = tctx.transport
      dest = getattr(transport, "dest", 0x50)
      info = _query_half(transport, dest, verbose=tctx.verbose)
      _print_half_status(tctx.side or "device", info)
      return

    devices = find_naya_serial_ports()
    if not devices:
      click.echo("No Naya Create devices found.")
      return

    if tctx.side:
      devices = [device for device in devices if device.side == tctx.side]
      if not devices:
        click.echo(f"No {tctx.side} half found.")
        return

    for index, device in enumerate(devices):
      if index > 0:
        click.echo()
      try:
        transport = tctx.connect_to(device)
        dest = getattr(transport, "dest", 0x50)
        info = _query_half(transport, dest, verbose=tctx.verbose)
        _print_half_status(device.description, info)
        transport.disconnect()
      except TransportError as error:
        click.echo(f"{device.description} ({device.port}): {error}")
