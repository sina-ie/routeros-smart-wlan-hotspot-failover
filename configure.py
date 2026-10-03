#!/usr/bin/env python3
"""
RouterOS Smart WLAN Hotspot Failover - Configuration Wizard
Decouples invariant RouterOS logic from device-specific configuration parameters.
Supports interactive wizard, config file loading, and example generation.
"""

import argparse
import datetime
import ipaddress
import json
import os
import re
import sys
from typing import Any, Callable, Dict, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "interfaces": {
        "lan_bridge": "bridge-LAN",
        "physical_wlan": "wlan1",
        "virtual_wlan": "wlan-virtual-ap",
    },
    "subnets": {
        "lan_cidr": "192.168.88.0/24",
        "modem_cidr": "192.168.1.0/24",
        "primary_gateway": "192.168.1.1",
    },
    "wireless": {
        "home_ssid": "Home-WiFi",
        "home_password": "ChangeMeHomePass",
        "home_channel_width": "20/40mhz-Ce",
        "home_frequency": 2452,
        "hotspot_ssid": "MobileHotspotSSID",
        "hotspot_password": "ChangeMeHotspotPass",
    },
    "schedule": {
        "night_start": "02:00:00",
        "night_stop": "07:00:00",
    },
}

TARGET_FILES = [
    "hotspot_dependencies.rsc",
    "hotspot_day_mode.rsc",
    "hotspot_night_mode.rsc",
    "hotspot_night_tick.rsc",
    "smart_switch_internet.rsc",
    "test_night_mode.rsc",
]

def validate_ipv4_network(val: str) -> str:
    """Validates and canonicalizes IPv4 CIDR notation (e.g. 192.168.88.0/24)."""
    val = val.strip()
    if "/" not in val:
        raise ValueError("Must include CIDR prefix length (e.g. /24)")
    try:
        net = ipaddress.IPv4Network(val, strict=False)
        return str(net)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid IPv4 CIDR network '{val}': {exc}")

def validate_ipv4_address(val: str) -> str:
    """Validates and normalizes IPv4 address (e.g. 192.168.1.1)."""
    try:
        addr = ipaddress.IPv4Address(val.strip())
        return str(addr)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid IPv4 address '{val}': {exc}")

def validate_time_format(val: str) -> str:
    """Validates and normalizes time into HH:MM:SS format."""
    try:
        dt = datetime.datetime.strptime(val.strip(), "%H:%M:%S")
        return dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        raise ValueError(f"Invalid time '{val}'. Expected HH:MM:SS format (e.g. 02:00:00)")

def validate_config(cfg: Dict[str, Any]) -> None:
    """Validates all critical network and time configuration fields in cfg."""
    try:
        cfg["subnets"]["lan_cidr"] = validate_ipv4_network(cfg["subnets"]["lan_cidr"])
        cfg["subnets"]["modem_cidr"] = validate_ipv4_network(cfg["subnets"]["modem_cidr"])
        cfg["subnets"]["primary_gateway"] = validate_ipv4_address(cfg["subnets"]["primary_gateway"])
        cfg["schedule"]["night_start"] = validate_time_format(cfg["schedule"]["night_start"])
        cfg["schedule"]["night_stop"] = validate_time_format(cfg["schedule"]["night_stop"])
    except KeyError as exc:
        raise ValueError(f"Missing required configuration key: {exc}")

def prompt_user(prompt: str, default: str, validator: Optional[Callable[[str], str]] = None) -> str:
    while True:
        res = input(f"{prompt} [{default}]: ").strip()
        val = res if res else default
        if validator is None:
            return val
        try:
            return validator(val)
        except ValueError as err:
            print(f"  [!] Error: {err}. Please try again.")

def calculate_offset_time(time_str: str, minutes_offset: int) -> str:
    """Calculates offset time in HH:MM:SS format."""
    dt = datetime.datetime.strptime(time_str, "%H:%M:%S")
    new_dt = dt + datetime.timedelta(minutes=minutes_offset)
    return new_dt.strftime("%H:%M:%S")

def extract_octet_prefix(cidr: str) -> str:
    """Extracts first three octets from CIDR (e.g. 192.168.88.0/24 -> 192.168.88)."""
    ip = cidr.split("/")[0]
    return ".".join(ip.split(".")[:3])

def extract_third_octet(cidr: str) -> str:
    """Extracts third octet (e.g. 192.168.88.0/24 -> 88)."""
    return cidr.split("/")[0].split(".")[2]

def build_replacements(cfg: Dict[str, Any]) -> Dict[str, str]:
    """Builds substitution mapping from parameters and derived logic."""
    lan_cidr = cfg["subnets"]["lan_cidr"]
    modem_cidr = cfg["subnets"]["modem_cidr"]
    lan_prefix = extract_octet_prefix(lan_cidr)
    lan_3rd = extract_third_octet(lan_cidr)
    modem_3rd = extract_third_octet(modem_cidr)

    night_start = cfg["schedule"]["night_start"]
    night_stop = cfg["schedule"]["night_stop"]

    # Derive watchdog tick boundaries (start 1 min early, stop 10 min early)
    tick_start = calculate_offset_time(night_start, -1)
    tick_stop = calculate_offset_time(night_stop, -10)

    collision_pattern = f"^192\\\\.168\\\\.({lan_3rd}|{modem_3rd})\\\\."
    lan_src_regex = f"^{lan_prefix.replace('.', '\\\\.')}\\\\."

    return {
        "bridge-LAN": cfg["interfaces"]["lan_bridge"],
        "wlan1": cfg["interfaces"]["physical_wlan"],
        "wlan-virtual-ap": cfg["interfaces"]["virtual_wlan"],
        "192.168.88.0/24": lan_cidr,
        "192.168.1.0/24": modem_cidr,
        "192.168.1.1": cfg["subnets"]["primary_gateway"],
        "^192\\.168\\.(88|1)\\.": collision_pattern,
        "^192\\.168\\.88\\.": lan_src_regex,
        "Home-WiFi": cfg["wireless"]["home_ssid"],
        "ChangeMeHomePass": cfg["wireless"]["home_password"],
        "MobileHotspotSSID": cfg["wireless"]["hotspot_ssid"],
        "ChangeMeHotspotPass": cfg["wireless"]["hotspot_password"],
        "02:00:00": night_start,
        "07:00:00": night_stop,
        "01:59:00": tick_start,
        "06:50:00": tick_stop,
    }

def run_wizard() -> Dict[str, Any]:
    print("=== Configuration Wizard ===")
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))

    cfg["interfaces"]["lan_bridge"] = prompt_user("LAN Bridge interface", cfg["interfaces"]["lan_bridge"])
    cfg["subnets"]["lan_cidr"] = prompt_user("LAN Subnet (CIDR)", cfg["subnets"]["lan_cidr"], validator=validate_ipv4_network)
    cfg["subnets"]["modem_cidr"] = prompt_user("Modem Management Subnet (CIDR)", cfg["subnets"]["modem_cidr"], validator=validate_ipv4_network)
    cfg["subnets"]["primary_gateway"] = prompt_user("Primary WAN Gateway IP", cfg["subnets"]["primary_gateway"], validator=validate_ipv4_address)

    cfg["wireless"]["home_ssid"] = prompt_user("Home Wi-Fi SSID", cfg["wireless"]["home_ssid"])
    cfg["wireless"]["home_password"] = prompt_user("Home Wi-Fi Password", cfg["wireless"]["home_password"])
    cfg["wireless"]["hotspot_ssid"] = prompt_user("Mobile Hotspot SSID", cfg["wireless"]["hotspot_ssid"])
    cfg["wireless"]["hotspot_password"] = prompt_user("Mobile Hotspot Password", cfg["wireless"]["hotspot_password"])

    cfg["schedule"]["night_start"] = prompt_user("Night Window Start (HH:MM:SS)", cfg["schedule"]["night_start"], validator=validate_time_format)
    cfg["schedule"]["night_stop"] = prompt_user("Night Window Stop (HH:MM:SS)", cfg["schedule"]["night_stop"], validator=validate_time_format)

    return cfg

def main():
    parser = argparse.ArgumentParser(description="RouterOS Script Generator")
    parser.add_argument("--config", "-c", type=str, help="Path to config.json")
    parser.add_argument("--example", action="store_true", help="Write config.example.json and exit")
    parser.add_argument("--output", "-o", type=str, default="dist", help="Output directory (default: dist)")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))

    if args.example:
        example_path = os.path.join(base_dir, "config.example.json")
        with open(example_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[✓] Example configuration written to: {example_path}")
        return

    print("================================================================")
    print(" RouterOS Smart WLAN Hotspot Failover - Configuration Generator ")
    print("================================================================\n")

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        try:
            validate_config(cfg)
        except ValueError as err:
            print(f"[!] Validation error in '{args.config}': {err}", file=sys.stderr)
            sys.exit(1)
        print(f"[✓] Loaded configuration from: {args.config}")
    else:
        cfg = run_wizard()
        save_cfg = prompt_user("\nSave configuration to config.json?", "yes")
        if save_cfg.lower().startswith("y"):
            with open(os.path.join(base_dir, "config.json"), "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            print("[✓] Saved configuration to config.json")

    replacements = build_replacements(cfg)
    out_dir = os.path.join(base_dir, args.output)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\nCompiling scripts into '{args.output}/' directory...")
    for fname in TARGET_FILES:
        src_path = os.path.join(base_dir, fname)
        dst_path = os.path.join(out_dir, fname)

        if not os.path.isfile(src_path):
            print(f"  [!] Missing template: {fname}, skipping")
            continue

        with open(src_path, "r", encoding="utf-8") as f:
            content = f.read()

        for old_val, new_val in replacements.items():
            content = content.replace(old_val, str(new_val))

        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"  [✓] Rendered: {args.output}/{fname}")

    lan_prefix = extract_octet_prefix(cfg["subnets"]["lan_cidr"])

    print("\n================================================================")
    print(f" Compilation finished successfully!")
    print(" Next steps:")
    print(f"   1. Upload: scp {args.output}/*.rsc admin@{lan_prefix}.1:/")
    print("   2. Import: /import file-name=hotspot_dependencies.rsc")
    print("================================================================")

if __name__ == "__main__":
    main()