# routeros-smart-wlan-hotspot-failover

An automated, policy-based failover and scheduling framework for single-radio MikroTik RouterOS devices (e.g., RB951G-2HnD, hEX, hAP series). It seamlessly switches Internet traffic between a primary wired WAN gateway and a mobile wireless hotspot during designated off-peak hours, while maintaining local Wi-Fi connectivity via a Virtual AP.

---

## Key Features

* **Single Radio AP/Station Multiplexing:** Utilizes a single physical Wi-Fi radio (`wlan1`) as a WAN station connecting to a mobile hotspot, while simultaneously serving local home devices via a Virtual AP (`wlan-virtual-ap`).
* **Policy-Based Routing (PBR):** Isolates the secondary WAN into a separate routing table (`to_Hotspot`), keeping the primary route (`main`) untouched.
* **Subnet Collision Detection:** Validates the IP received from the mobile hotspot to prevent overlapping with local LAN or modem management subnets.
* **Automatic Watchdog:** Periodically verifies station connectivity during the active window and triggers reconnection if the phone leaves or toggles hotspot.
* **Safe State Persistence:** Virtual AP interfaces are enabled/disabled rather than deleted, preventing orphan `*` bridge port memory leaks in RouterOS.
* **Interactive Python Generator:** Includes `configure.py` to customize all parameters for your router setup.

---

## Architecture Overview

```text
+------------------------------------------------------------------------+
|                          MikroTik RouterOS                             |
|                                                                        |
|  Day Mode (07:00 - 02:00)             Night Mode (02:00 - 07:00)       |
|  ------------------------             --------------------------       |
|  wlan1: Master AP (Home-WiFi)         wlan1: Station -> Mobile Hotspot  |
|                                       wlan-virtual-ap: Home-WiFi       |
|  WAN: Primary Ethernet Gateway        WAN: Mobile Hotspot (PBR FIB)    |
|  Routing Table: main                  Routing Table: to_Hotspot        |
+------------------------------------------------------------------------+
```

---

## Project Structure

* `hotspot_dependencies.rsc`: Base configuration (Security profiles, Routing table, Mangle rules, NAT, and Schedulers).
* `hotspot_day_mode.rsc`: Switches routing back to Primary WAN and converts `wlan1` to Master AP mode.
* `hotspot_night_mode.rsc`: Connects `wlan1` to mobile hotspot, launches Virtual AP, and routes traffic via `to_Hotspot`.
* `hotspot_night_tick.rsc`: Periodic watchdog checking link state during the night window.
* `smart_switch_internet.rsc`: Manual one-click toggle script.
* `test_night_mode.rsc`: Self-test script validating DHCP, Mangle state, and external ICMP ping.
* `configure.py`: Interactive CLI wizard to generate personalized scripts for your network.

---

## Quick Start

### 1. Generate Your Custom Configuration
Run the interactive configuration wizard:
```bash
python3 configure.py
```
Follow the prompts to enter your SSIDs, passwords, subnets, and schedule times. The customized `.rsc` files will be placed into the `dist/` directory.

### 2. Import onto MikroTik Router
Upload the generated scripts using SCP, FTP, or WinBox:
```bash
scp dist/*.rsc admin@192.168.88.1:/
```

In the RouterOS terminal, import the base dependencies first:
```routeros
/import file-name=hotspot_dependencies.rsc
```

Add the operational scripts to RouterOS:
```routeros
/system script add name=HOTSPOT_DAY_MODE source=[/file get hotspot_day_mode.rsc contents]
/system script add name=HOTSPOT_NIGHT_MODE source=[/file get hotspot_night_mode.rsc contents]
/system script add name=HOTSPOT_NIGHT_TICK source=[/file get hotspot_night_tick.rsc contents]
/system script add name=SMART_SWITCH_INTERNET source=[/file get smart_switch_internet.rsc contents]
/system script add name=TEST_NIGHT_MODE source=[/file get test_night_mode.rsc contents]
```

### 3. Verify
Run the test script to verify hotspot connectivity:
```routeros
/system script run TEST_NIGHT_MODE
```

---

## License
MIT