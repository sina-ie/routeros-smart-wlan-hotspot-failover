# =====================================================================
# RouterOS Smart WLAN Hotspot Failover - Base Infrastructure Setup
# Target: RouterOS v7.x
# =====================================================================

# 1. Clean up stale/orphan bridge ports (references matching dynamic '*' IDs)
/interface bridge port remove [find where interface~"^\\*"]

# 2. Wireless Security Profiles (Hotspot client & Home Access Point)
/interface wireless security-profiles
add authentication-types=wpa2-psk mode=dynamic-keys name=Home_Profile supplicant-identity="" wpa2-pre-shared-key="ChangeMeHomePass"
add authentication-types=wpa2-psk comment="[SECURITY-PROFILE] Mobile Hotspot" mode=dynamic-keys name=Hotspot_Profile supplicant-identity=MikroTik wpa2-pre-shared-key="ChangeMeHotspotPass"

# 3. Wireless Master Interface and Virtual AP Definition
/interface wireless
set [ find default-name=wlan1 ] band=2ghz-onlyn comment="[WAN-WIFI] Receiver from Mobile Hotspot" \
    disabled=no frequency=auto security-profile=Hotspot_Profile ssid="MobileHotspotSSID" wps-mode=disabled

:if ([:len [/interface wireless find where name="wlan-virtual-ap"]] = 0) do={
    /interface wireless add disabled=no master-interface=wlan1 name=wlan-virtual-ap \
        security-profile=Home_Profile ssid="Home-WiFi" wps-mode=disabled
}

# Attach Virtual AP to LAN Bridge
:if ([:len [/interface bridge port find where interface=wlan-virtual-ap]] = 0) do={
    /interface bridge port add bridge=bridge-LAN interface=wlan-virtual-ap
}

# 4. Policy-Based Routing (FIB) Table for Hotspot WAN
/routing table
add comment="[ROUTING-TABLE] Hotspot routing table" fib name=to_Hotspot

# 5. DHCP Client for Hotspot WAN
/ip dhcp-client
add comment="[DHCP-CLIENT] Mobile Hotspot -> to_Hotspot table" default-route-tables=to_Hotspot \
    disabled=yes interface=wlan1 name=client-hotspot use-peer-dns=no use-peer-ntp=no

# 6. RFC1918 Private Address List
/ip firewall address-list
add address=10.0.0.0/8 list=RFC1918
add address=172.16.0.0/12 list=RFC1918
add address=192.168.0.0/16 list=RFC1918

# 7. Policy-Based Routing Firewall Rules (Mangle)
/ip firewall mangle
# Ensure upstream modem management network remains directly reachable
add action=accept chain=prerouting comment="[MANGLE-BYPASS] Primary modem subnet bypass" \
    dst-address=192.168.1.0/24 src-address=192.168.88.0/24

# Route LAN client traffic to Hotspot
add action=mark-routing chain=prerouting comment="=== TOGGLE_INTERNET_HOTSPOT (LAN) ===" \
    disabled=yes dst-address=!192.168.88.0/24 dst-address-type=!local \
    new-routing-mark=to_Hotspot passthrough=no src-address=192.168.88.0/24

# Route local router generated traffic (DNS, NTP, checks) to Hotspot
add action=mark-routing chain=output comment="=== TOGGLE_INTERNET_HOTSPOT (router) ===" \
    disabled=yes dst-address-list=!RFC1918 dst-address-type=!local \
    new-routing-mark=to_Hotspot passthrough=no

# 8. Consolidated Outbound NAT Masquerade
/ip firewall nat
add action=masquerade chain=srcnat comment="[NAT] WAN Outbound Masquerade" out-interface-list=WAN

# 9. Secondary Route Fallback (Routing to primary gateway if hotspot drops)
/ip route
add check-gateway=ping comment="[ROUTE-FALLBACK] to_Hotspot falls back to Primary WAN" \
    distance=10 dst-address=0.0.0.0/0 gateway=192.168.1.1 routing-table=to_Hotspot

# 10. Automated System Schedulers
/system scheduler
add comment="[SCHEDULER] Morning restore to primary WAN" interval=1d \
    name=Sched_Hotspot_Day_Restore on-event=HOTSPOT_DAY_MODE policy=read,write,policy,test \
    start-time=07:00:00 start-date=2026-01-01
add comment="[SCHEDULER] Night watchdog check" interval=15m \
    name=Sched_Hotspot_Tick on-event=HOTSPOT_NIGHT_TICK \
    policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    start-time=02:00:00 start-date=2026-01-01