#!/usr/bin/env python3
"""
Unit tests for configure.py.
Covers input validation, derived offsets, substitution generation, and template rendering.
"""

import copy
import os
import tempfile
import unittest

from configure import (
    DEFAULT_CONFIG,
    TARGET_FILES,
    build_replacements,
    calculate_offset_time,
    extract_octet_prefix,
    extract_third_octet,
    validate_config,
    validate_ipv4_address,
    validate_ipv4_network,
    validate_time_format,
)


class TestValidation(unittest.TestCase):
    def test_validate_ipv4_network_valid(self):
        self.assertEqual(validate_ipv4_network("192.168.88.0/24"), "192.168.88.0/24")
        self.assertEqual(validate_ipv4_network(" 10.0.0.0/8 "), "10.0.0.0/8")
        # Non-strict network check normalizes host bits to base subnet
        self.assertEqual(validate_ipv4_network("192.168.88.50/24"), "192.168.88.0/24")

    def test_validate_ipv4_network_missing_mask(self):
        with self.assertRaises(ValueError):
            validate_ipv4_network("192.168.88.1")

    def test_validate_ipv4_network_invalid(self):
        with self.assertRaises(ValueError):
            validate_ipv4_network("999.999.999.999/24")
        with self.assertRaises(ValueError):
            validate_ipv4_network("not-an-ip/24")

    def test_validate_ipv4_address_valid(self):
        self.assertEqual(validate_ipv4_address("192.168.1.1"), "192.168.1.1")
        self.assertEqual(validate_ipv4_address(" 10.10.10.1 "), "10.10.10.1")

    def test_validate_ipv4_address_invalid(self):
        with self.assertRaises(ValueError):
            validate_ipv4_address("192.168.1.1/24")
        with self.assertRaises(ValueError):
            validate_ipv4_address("300.1.1.1")

    def test_validate_time_format_valid(self):
        self.assertEqual(validate_time_format("02:00:00"), "02:00:00")
        self.assertEqual(validate_time_format("23:59:59"), "23:59:59")

    def test_validate_time_format_invalid(self):
        with self.assertRaises(ValueError):
            validate_time_format("2:00")
        with self.assertRaises(ValueError):
            validate_time_format("25:00:00")
        with self.assertRaises(ValueError):
            validate_time_format("02:60:00")

    def test_validate_config_valid(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        validate_config(cfg)
        self.assertEqual(cfg["subnets"]["lan_cidr"], "192.168.88.0/24")

    def test_validate_config_missing_key(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        del cfg["subnets"]["lan_cidr"]
        with self.assertRaises(ValueError):
            validate_config(cfg)


class TestTimeAndSubnetCalculations(unittest.TestCase):
    def test_calculate_offset_time(self):
        self.assertEqual(calculate_offset_time("02:00:00", -1), "01:59:00")
        self.assertEqual(calculate_offset_time("07:00:00", -10), "06:50:00")
        # Across midnight boundary
        self.assertEqual(calculate_offset_time("00:05:00", -10), "23:55:00")

    def test_extract_octet_prefix(self):
        self.assertEqual(extract_octet_prefix("192.168.88.0/24"), "192.168.88")
        self.assertEqual(extract_octet_prefix("10.5.1.0/24"), "10.5.1")

    def test_extract_third_octet(self):
        self.assertEqual(extract_third_octet("192.168.88.0/24"), "88")
        self.assertEqual(extract_third_octet("172.16.50.0/24"), "50")


class TestSubstitutionLogic(unittest.TestCase):
    def test_build_replacements_default(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        replacements = build_replacements(cfg)

        self.assertEqual(replacements["bridge-LAN"], "bridge-LAN")
        self.assertEqual(replacements["192.168.88.0/24"], "192.168.88.0/24")
        self.assertEqual(replacements["^192\\.168\\.(88|1)\\."], "^192\\.168\\.(88|1)\\.")
        self.assertEqual(replacements["^192\\.168\\.88\\."], "^192\\.168\\.88\\.")
        self.assertEqual(replacements["01:59:00"], "01:59:00")
        self.assertEqual(replacements["06:50:00"], "06:50:00")

    def test_build_replacements_custom(self):
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["subnets"]["lan_cidr"] = "192.168.10.0/24"
        cfg["subnets"]["modem_cidr"] = "192.168.20.0/24"
        cfg["schedule"]["night_start"] = "01:30:00"
        cfg["schedule"]["night_stop"] = "06:00:00"

        replacements = build_replacements(cfg)
        self.assertEqual(replacements["^192\\.168\\.(88|1)\\."], "^192\\.168\\.(10|20)\\.")
        self.assertEqual(replacements["^192\\.168\\.88\\."], "^192\\.168\\.10\\.")
        self.assertEqual(replacements["01:59:00"], "01:29:00")
        self.assertEqual(replacements["06:50:00"], "05:50:00")


class TestTemplateRendering(unittest.TestCase):
    def test_all_target_templates_exist_and_render(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cfg = copy.deepcopy(DEFAULT_CONFIG)
        cfg["wireless"]["home_ssid"] = "TestHomeSSID"
        cfg["wireless"]["hotspot_ssid"] = "TestHotspotSSID"
        cfg["interfaces"]["lan_bridge"] = "bridge-CUSTOM"

        replacements = build_replacements(cfg)

        with tempfile.TemporaryDirectory() as tmp_dir:
            for fname in TARGET_FILES:
                src_path = os.path.join(base_dir, fname)
                self.assertTrue(os.path.isfile(src_path), f"Missing target template: {fname}")

                with open(src_path, "r", encoding="utf-8") as f:
                    content = f.read()

                for old_val, new_val in replacements.items():
                    content = content.replace(old_val, str(new_val))

                out_file = os.path.join(tmp_dir, fname)
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(content)

                with open(out_file, "r", encoding="utf-8") as f:
                    rendered = f.read()

                # Check that replaced values actually appear
                if "bridge-LAN" in open(src_path, "r", encoding="utf-8").read():
                    self.assertIn("bridge-CUSTOM", rendered)
                    self.assertNotIn("bridge-LAN", rendered)

                if "MobileHotspotSSID" in open(src_path, "r", encoding="utf-8").read():
                    self.assertIn("TestHotspotSSID", rendered)
                    self.assertNotIn("MobileHotspotSSID", rendered)


if __name__ == "__main__":
    unittest.main()