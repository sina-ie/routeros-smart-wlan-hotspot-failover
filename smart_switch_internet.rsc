# Script: SMART_SWITCH_INTERNET
# Manual toggle between Primary WAN and Hotspot WAN

:local ids [/ip firewall mangle find where comment~"TOGGLE_INTERNET_HOTSPOT"]
:if ([:len $ids] = 0) do={ /log error "TOGGLE_INTERNET_HOTSPOT mangle rule not found"; :error "rule not found" }
:if ([/ip firewall mangle get [:pick $ids 0] disabled]) do={
    /system script run HOTSPOT_NIGHT_MODE
} else={
    /system script run HOTSPOT_DAY_MODE
}