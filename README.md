# Plum ecoMAX for Home Assistant
[![CI](https://github.com/lachand/plum_ecomax/actions/workflows/ci.yml/badge.svg)](https://github.com/lachand/plum_ecomax/actions/workflows/ci.yml)
[![Documentation](https://github.com/lachand/plum_ecomax/actions/workflows/doc.yaml/badge.svg)](https://github.com/lachand/plum_ecomax/actions/workflows/doc.yaml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

**Plum ecoMAX** is a custom integration for Home Assistant that allows you to monitor and control Plum ecoMAX boiler controllers via a network connection (RS485/Ethernet).

{% if installed %}
## Getting Started

Once installed via HACS, you can set up the integration via the Home Assistant generic **Settings** > **Devices & Services** > **Add Integration** menu. Search for "Plum ecoMAX".
{% endif %}

## Features

This integration aims to support the primary functions of the ecoMAX controller:

* **Monitoring:** Read current temperatures (feeder, boiler, outside, etc.), boiler status, and fuel consumption.
* **Control:** Adjust target temperatures and operation modes, per-circuit heating curves, and the DHW anti-legionella cycle.
* **Sensors:** Binary sensors for pumps and fan status, plus the boiler's serial number (shown on the device page) and any circuit names configured on the physical panel.
* **Diagnostics & alerts:** A "manual mode active" binary sensor, coarse alarm-bit indicators, and repair issues in Settings → Repairs when an alarm is active, a write is rejected by the boiler, or the connection is lost.
* **Reference values:** Buttons to save the current heating-curve/DHW configuration as a reference snapshot and restore it later.
* **Batched, persistent connection:** Several parameters are read per network request instead of one connection per value, and the TCP connection to the boiler is kept open across polls (with automatic reconnection) instead of reconnecting every time.
* **Diagnostics download:** Downloadable diagnostics snapshot from the device page (Settings → Devices & Services → Plum EcoMAX → Download diagnostics).
* **Reconfigurable:** IP address, port, credentials, active circuits, and polling interval can be changed later via **Reconfigure** on the integration, without deleting and re-adding it.

### A note on "force" parameters

Switches like *Force pompe ECS → ballon solaire* write the same parameter the boiler's own front panel uses, but the boiler only applies it while the **physical panel is in manual mode**. This is a limitation of the boiler's firmware, not of this integration — outside manual mode, the boiler's automatic control silently overrides the forced value. The "Manual mode active" binary sensor reflects whether that condition is currently met.

## Installation

### Option 1: HACS (Recommended)
1. Open HACS in your Home Assistant instance.
2. Go to "Integrations" and click the three dots in the top right corner.
3. Select "Custom repositories".
4. Add the URL of this repository: `https://github.com/lachand/plum_ecomax`.
5. Select **Integration** as the category.
6. Click **Add** and then install the integration.
7. **Restart Home Assistant.**

### Option 2: Manual Installation
1. Download the `plum_ecomax` directory from the `custom_components` folder in this repository.
2. Copy the directory into your Home Assistant `<config>/custom_components/` directory.
3. **Restart Home Assistant.**

## Configuration

Configuration is done via the **User Interface (Config Flow)**.
You will need to provide:
* **IP Address:** The local IP address of your ecoMAX module.
* **Port:** The port used for communication (default usually 8899).
* **Username / Password:** Admin credentials for the boiler.
* **Active Heating Circuits:** Only the circuits you select here get entities — unused circuits (1-7) in the boiler's parameter catalog are skipped.
* **Polling interval:** How often (in seconds, 10-300) the integration reads from the boiler. Defaults to 30s.

Any of these can be changed later via **Reconfigure** on the integration card, without removing it.

## Development

Unit and regression tests live in `tests/` (`pytest tests/`), and run automatically in CI on every push/PR alongside `hassfest` and HACS validation. See `DP_INVENTORY.md` for the catalog of boiler parameters not yet exposed as entities.

## Disclaimer

This integration is developed by the community and is **not** officially affiliated with or endorsed by Plum Sp. z o.o. Use it at your own risk.

---
If you encounter any issues, please open a ticket on [GitHub Issues](https://github.com/lachand/plum_ecomax/issues).
