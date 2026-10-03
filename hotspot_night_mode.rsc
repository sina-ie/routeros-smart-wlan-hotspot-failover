# Script: HOTSPOT_NIGHT_MODE
# Connects to Mobile Hotspot WAN while keeping Home Wi-Fi available via Virtual AP

/interface bridge port remove [find where interface=wlan1]
/interface wireless set [find default-name=wlan1] mode=station ssid="MobileHotspotSSID" \
    security-profile=Hotspot_Profile band=2ghz-onlyn channel-width=20mhz frequency=auto scan-list=default wps-mode=disabled disabled=no

:if ([:len [/interface wireless find where name="wlan-virtual-ap"]] = 0) do={
    /interface wireless add name=wlan-virtual-ap master-interface=wlan1 mode=ap-bridge ssid="Home-WiFi" \
        security-profile=Home_Profile wps-mode=disabled disabled=no
} else={
    /interface wireless set [find name="wlan-virtual-ap"] disabled=no
}

:if ([:len [/interface bridge port find where interface=wlan-virtual-ap]] = 0) do={
    /interface bridge port add bridge=bridge-LAN interface=wlan-virtual-ap
}
:if ([:len [/interface list member find where list=WAN interface=wlan1]] = 0) do={
    /interface list member add list=WAN interface=wlan1
}
/ip dhcp-client enable [find where interface=wlan1]

:local i 0
:local bound false
:while ($i < 15 && !$bound) do={
    :delay 1s
    :set i ($i + 1)
    :if ([/ip dhcp-client get [find interface=wlan1] status] = "bound") do={ :set bound true }
}

:local addr ""
:if ($bound) do={ :set addr [/ip dhcp-client get [find interface=wlan1] address] }

# Validate DHCP lease and ensure no subnet collisions with LAN or Modem
:if ($bound && !($addr~"^192\\.168\\.(88|1)\\.")) do={
    :local ids [/ip firewall mangle find where comment~"TOGGLE_INTERNET_HOTSPOT"]
    /ip firewall mangle enable $ids
    /ip firewall connection remove [find where src-address~"^192\\.168\\.88\\."]
    /interface bridge set [find name="bridge-LAN"] comment="*** ROUTING VIA: MOBILE HOTSPOT ***"
    /log warning ("=== NIGHT mode: Connected to Hotspot, address " . $addr . " ===")
} else={
    :if ($bound) do={ /log error ("Hotspot subnet " . $addr . " collides with local subnets - staying on Primary WAN") } else={ /log warning "Hotspot unavailable - staying on Primary WAN" }
    /system script run HOTSPOT_DAY_MODE
}