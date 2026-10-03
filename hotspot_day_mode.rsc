# Script: HOTSPOT_DAY_MODE
# Reverts routing to Primary WAN and reconfigures wlan1 as Master AP

:local ids [/ip firewall mangle find where comment~"TOGGLE_INTERNET_HOTSPOT"]
:local wasOn false
:if ([:len $ids] > 0) do={
    :if ([/ip firewall mangle get [:pick $ids 0] disabled] = false) do={ :set wasOn true }
    /ip firewall mangle disable $ids
}

/ip dhcp-client disable [find where interface=wlan1]
/interface list member remove [find where list=WAN interface=wlan1]

# Disable Virtual AP without removing to preserve bridge port membership
:if ([:len [/interface wireless find where name="wlan-virtual-ap"]] > 0) do={
    /interface wireless set [find name="wlan-virtual-ap"] disabled=yes
}

:if ([/interface wireless get [find default-name=wlan1] mode] != "ap-bridge") do={
    /interface wireless set [find default-name=wlan1] mode=ap-bridge ssid="Home-WiFi" \
        security-profile=Home_Profile band=2ghz-onlyn channel-width=20/40mhz-Ce frequency=2452 wps-mode=disabled disabled=no
}
:if ([:len [/interface bridge port find where interface=wlan1]] = 0) do={
    /interface bridge port add bridge=bridge-LAN interface=wlan1
}
:if ($wasOn) do={
    /ip firewall connection remove [find where src-address~"^192\\.168\\.88\\."]
}
/interface bridge set [find name="bridge-LAN"] comment="=== ROUTING VIA: PRIMARY GATEWAY ==="
/log warning "=== DAY mode: Primary WAN active, Home Wi-Fi on wlan1 ==="