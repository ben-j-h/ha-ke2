# KE2 Therm — Home Assistant integration

Local-polling integration for **KE2 Therm** refrigeration controllers (KE2 Temp,
KE2 Low Temp, KE2 Adaptive, …) through the **KE2 LDA** (Local Area Dashboard and Alarms) network
box. It talks to the LDA's JSON API on your LAN: no cloud, no KE2 account.

Built on [`pyke2`](https://github.com/ben-j-h/pyke2). The reverse-engineering notes are
in that repo's [`research/`](https://github.com/ben-j-h/pyke2/tree/main/research).

## Features

Entities are generated from each controller's own field schema, so any KE2 model on the
LDA's Modbus bus shows up as its own device:

- **Climate**: room temperature, setpoint, and cooling / idle / defrosting from the
  relay and mode. Attributes include cut-in (setpoint + differential), mode, alarms and
  probe fault. Off/on is available on models with *Manual Control*.
- **Sensors**: every numeric status field (room and coil temperature, …), mode, alarm
  count with the active alarm list, and Modbus comm timeouts (diagnostic). A shorted or
  open probe (`999.9` / `888.8`) reads *unavailable* rather than a bogus number.
- **Binary sensors**: relays (cooling, fan, defrost …), one problem sensor per alarm,
  and room probe fault.
- **Numbers / selects / times** for every writable setting: differential, defrosts per
  day, defrost duration, alarm offsets and delay, max compressor starts per hour, the
  controller clock, and custom defrost start times (disabled by default). Ranges and
  units come from the controller. Modbus address and temperature units are only created
  with the *advanced* option.
- **Buttons**: *Sync controller clock* (the KE2 clock is free-running and drifts) and
  *Next mode* (disabled by default).
- **`ke2.set_value`** service for anything an entity can't express, e.g. `24:00` to
  disable a custom defrost start.
- Every write is validated against the controller's limits, then re-read to confirm it
  stuck. A failure raises an error your automation can see.

## Requirements

- Home Assistant **2026.9** or newer.
- A KE2 LDA reachable on your network **by IP address**. The LDA redirects requests
  that use its hostname to KE2's cloud, so give it a DHCP reservation.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/ben-j-h/ha-ke2`,
   category **Integration**.
2. Install **KE2 Therm**, restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → KE2 Therm**. Enter the LDA's IP
   and credentials (factory default `ke2admin` / `ke2admin`; reading needs none).

### Manual

Copy `custom_components/ke2/` into `config/custom_components/` and restart.

## Notes

- **Don't plug the LDA's LAN port into your network.** It runs a DHCP server. Use the
  WAN port or Wi-Fi.
- The LDA occasionally drops off the network or loses its link to the controller.
  Entities go unavailable and recover on the next poll. If yours needs a hard
  power-cycle to recover, put it on a smart plug and automate a reboot when the
  climate entity has been unavailable for a while.
- `Max compressor starts per hour` limits how often the **controller** starts the
  compressor. It can't stop a condensing unit's own pressure switch from short-cycling
  the compressor.

## Development

```bash
uv sync
uv run pytest
uv run ruff check custom_components tests
```

Tests drive the integration against an in-memory LDA built from responses captured
from a real KE2 Temp.

Not affiliated with KE2 Therm Solutions.
