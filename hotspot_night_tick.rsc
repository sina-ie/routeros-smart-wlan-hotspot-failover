# Script: HOTSPOT_NIGHT_TICK
# Night watchdog to ensure Hotspot connection remains active within window

:local t [/system clock get time]
:if ($t >= 01:59:00 && $t < 06:50:00) do={
    :local currentStatus [/interface wireless get [find default-name=wlan1] running]
    :local currentMode [/interface wireless get [find default-name=wlan1] mode]
    :if ($currentMode != "station" || $currentStatus = false) do={
        :log warning "=== [NIGHT WATCHDOG] Mobile Hotspot disconnected. Reconnecting... ==="
        /system script run HOTSPOT_NIGHT_MODE
    }
}