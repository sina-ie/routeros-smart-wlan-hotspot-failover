# routeros-smart-wlan-hotspot-failover

[![CI](https://github.com/sina-ie/routeros-smart-wlan-hotspot-failover/actions/workflows/ci.yml/badge.svg)](https://github.com/sina-ie/routeros-smart-wlan-hotspot-failover/actions/workflows/ci.yml)
[![RouterOS](https://img.shields.io/badge/RouterOS-v6%20%7C%20v7-blue.svg)](https://mikrotik.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8%2B-brightgreen.svg)](configure.py)

An automated, policy-based failover and scheduling framework for single-radio MikroTik RouterOS devices (e.g., RB951G-2HnD, hEX, hAP series). It seamlessly switches Internet traffic between a primary wired WAN gateway and a mobile wireless hotspot during designated off-peak hours, while maintaining local Wi-Fi connectivity via a Virtual AP.

---

## Release v1.0.1 Highlights

* **Automated CI Pipeline:** Continuous Integration via GitHub Actions testing across Python 3.8 through 3.12.
* **Strict Input Validation:** Runtime validation and canonicalization of IPv4 CIDR notations, unicast IP addresses, and 24-hour time patterns (`HH:MM:SS`).
* **Decoupled Architecture:** Full parameter externalization via `config.json` with dynamic derivation of watchdog tick intervals and collision avoidance regular expressions.
* **Standardized Testing:** Complete unit test suite (`test_configure.py`) validating edge cases, boundary offsets across midnight, and template integrity.

## Key Features

* **Single Radio AP/Station Multiplexing:** Utilizes a single physical Wi-Fi radio (`wlan1`) as a WAN station connecting to a mobile hotspot, while simultaneously serving local home devices via a Virtual AP (`wlan-virtual-ap`).
* **Policy-Based Routing (PBR):** Isolates the secondary WAN into a separate routing table (`to_Hotspot`), keeping the primary route (`main`) untouched.
* **Subnet Collision Detection:** Validates the IP received from the mobile hotspot to prevent overlapping with local LAN or modem management subnets.
* **Automatic Watchdog:** Periodically verifies station connectivity during the active window and triggers reconnection if the phone leaves or toggles hotspot.
* **Safe State Persistence:** Virtual AP interfaces are enabled/disabled rather than deleted, preventing orphan `*` bridge port memory leaks in RouterOS.
* **Interactive Python Generator:** Includes `configure.py` to customize all parameters for your router setup.

---

## Architecture Overview

### Single-Radio Hardware Multiplexing
In standard single-radio hardware, a Wi-Fi interface can only listen on one channel at a time. When entering Night Mode, `wlan1` shifts into `station` mode to connect to the external hotspot. A Virtual AP (`wlan-virtual-ap`) is simultaneously attached to `wlan1` to serve local clients on that same channel.

```text
                       +---------------------------------------+
                       |           Mobile Hotspot              |
                       +---------------------------------------+
                                          ▲
                                          │ 802.11 Station Link (WAN)
                                          ▼
+-----------------------------------------------------------------------------------+
| MikroTik RouterOS                                                                 |
|                                                                                   |
|   [ Physical Radio: wlan1 ] (Mode: station, locks to Hotspot RF Channel)          |
|               │                                                                   |
|               ├──> DHCP Client (table: to_Hotspot) -> PBR Firewall Mangle -> NAT |
|               │                                                                   |
|   [ Master/Slave Hook ]                                                           |
|               │                                                                   |
|   [ Virtual AP: wlan-virtual-ap ] (SSID: Home-WiFi, Mode: ap-bridge)              |
|               │                                                                   |
|               └──> [ bridge-local ] <──> Local LAN Ports (192.168.88.0/24)        |
+-----------------------------------------------------------------------------------+
                                          ▲
                                          │ 802.11 AP Broadcast
                                          ▼
                       +---------------------------------------+
                       |         Local Wireless Clients        |
                       +---------------------------------------+
```

### Operational Modes

| Component | Day Mode (`07:00 - 02:00`) | Night Mode (`02:00 - 07:00`) |
| :--- | :--- | :--- |
| **Physical Radio (`wlan1`)** | `ap-bridge` (SSID: Home-WiFi) | `station` (Connected to Mobile Hotspot) |
| **Virtual AP (`wlan-virtual-ap`)** | Disabled | Enabled (SSID: Home-WiFi, bridged to LAN) |
| **Active Internet Gateway** | Primary Wired Gateway | Mobile Wireless Hotspot |
| **Routing Table Used** | `main` | `to_Hotspot` (via PBR Mangle) |
| **Watchdog Status** | Inactive | Active (`HOTSPOT_NIGHT_TICK` every 2-3 mins) |

---

## Logic & State Transitions

1. **Day to Night Switch (`hotspot_night_mode.rsc`)**:
   * Reconfigures `wlan1` to `station` mode with mobile hotspot credentials.
   * Enables `wlan-virtual-ap` and attaches it to `bridge-local`.
   * Starts DHCP client on `wlan1` with routing mark `to_Hotspot`.
   * Evaluates assigned IP against local subnets (`192.168.88.0/24` and modem IPs) to prevent routing collisions.
   * Activates firewall mangle rules to route traffic through `to_Hotspot`.

2. **Night Watchdog (`hotspot_night_tick.rsc`)**:
   * Periodically validates connection state by pinging public DNS (`8.8.8.8`) via routing table `to_Hotspot`.
   * If unreachable or if `wlan1` is unassociated, cycles the wireless interface to re-trigger association without taking down the wired LAN.

3. **Night to Day Switch (`hotspot_day_mode.rsc`)**:
   * Disables firewall mangle rules and releases DHCP on `wlan1`.
   * Disables `wlan-virtual-ap`.
   * Restores `wlan1` to `ap-bridge` mode.
   * Restores all traffic routing to the `main` table via the wired gateway.

4. **Manual Override (`smart_switch_internet.rsc`)**:
   * Allows on-demand switching between modes at any time outside the scheduled window.
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

### Clone the Repository
```bash
git clone https://github.com/sina-ie/routeros-smart-wlan-hotspot-failover.git
cd routeros-smart-wlan-hotspot-failover
```

### 1. Generate Your Custom Configuration
You can generate scripts either interactively or via a declarative JSON file:

**Option A: Using the CLI Wizard**
```bash
python3 configure.py
```

**Option B: Using a Configuration File**
1. Export the template:
```bash
python3 configure.py --example
cp config.example.json config.json
```
2. Edit `config.json` with your network values, then compile:
```bash
python3 configure.py --config config.json
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