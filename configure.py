#!/usr/bin/env python3
"""
RouterOS Smart WLAN Hotspot Failover - Configuration Wizard
Generates custom .rsc files for target MikroTik routers.
"""

import os
import sys

def prompt_user(prompt: str, default: str) -> str:
    res = input(f"{prompt} [{default}]: ").strip()
    return res if res else default

def main():
    print("================================================================")
    print(" RouterOS Smart WLAN Hotspot Failover - Configuration Generator ")
    print("================================================================\n")

    # Network & Interface parameters
    lan_bridge = prompt_user("LAN Bridge interface name", "bridge-LAN")
    lan_subnet = prompt_user("LAN Subnet (CIDR)", "192.168.88.0/24")
    lan_ip_prefix = ".".join(lan_subnet.split(".")[:3])

    primary_gw = prompt_user("Primary WAN Gateway IP", "192.168.1.1")
    modem_subnet = prompt_user("Modem Management Subnet (CIDR)", "192.168.1.0/24")

    # Wireless parameters
    home_ssid = prompt_user("Home Wi-Fi SSID", "Home-WiFi")
    home_pass = prompt_user("Home Wi-Fi WPA2 Password", "MyHomeSecretPass")
    hotspot_ssid = prompt_user("Mobile Hotspot SSID", "MobileHotspotSSID")
    hotspot_pass = prompt_user("Mobile Hotspot WPA2 Password", "MyHotspotSecretPass")

    # Schedules
    night_start = prompt_user("Night Window Start Time (HH:MM:SS)", "02:00:00")
    night_stop = prompt_user("Night Window Stop Time (HH:MM:SS)", "07:00:00")

    replacements = {
        "bridge-LAN": lan_bridge,
        "192.168.88.0/24": lan_subnet,
        "192\\.168\\.88\\.": lan_ip_prefix.replace(".", "\\\\.") + "\\\\.",
        "192.168.1.1": primary_gw,
        "192.168.1.0/24": modem_subnet,
        "Home-WiFi": home_ssid,
        "ChangeMeHomePass": home_pass,
        "MobileHotspotSSID": hotspot_ssid,
        "ChangeMeHotspotPass": hotspot_pass,
        "02:00:00": night_start,
        "07:00:00": night_stop,
    }

    target_files = [
        "hotspot_dependencies.rsc",
        "hotspot_day_mode.rsc",
        "hotspot_night_mode.rsc",
        "hotspot_night_tick.rsc",
        "smart_switch_internet.rsc",
        "test_night_mode.rsc",
    ]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base_dir, "dist")
    os.makedirs(out_dir, exist_ok=True)

    print("\nGenerating customized scripts into 'dist/' directory...")
    for fname in target_files:
        src_path = os.path.join(base_dir, fname)
        dst_path = os.path.join(out_dir, fname)

        if not os.path.isfile(src_path):
            print(f"  [!] Source file not found, skipping: {fname}")
            continue

        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        for old_val, new_val in replacements.items():
            content = content.replace(old_val, new_val)

        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  [✓] Created: dist/{fname}")

    print("\n================================================================")
    print(" All scripts successfully generated in 'dist/'!")
    print(" Next steps:")
    print(f"   1. Upload: scp dist/*.rsc admin@{lan_ip_prefix}.1:/")
    print("   2. Import dependencies: /import file-name=hotspot_dependencies.rsc")
    print("================================================================")

if __name__ == "__main__":
    main()