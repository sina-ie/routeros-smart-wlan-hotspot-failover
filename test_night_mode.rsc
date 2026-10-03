# Script: TEST_NIGHT_MODE
# Simulation test for Hotspot connection and routing validation

:put "============================================="
:put "   STARTING HOTSPOT FAILOVER SIMULATION TEST "
:put "============================================="

:log warning "=== [TEST] Enabling Hotspot Mode... ==="
:put "[+] Executing HOTSPOT_NIGHT_MODE script..."
/system script run HOTSPOT_NIGHT_MODE
:delay 3s

:local mangleID [/ip firewall mangle find comment~"TOGGLE_INTERNET_HOTSPOT"]
:if ([:len $mangleID] > 0) do={
    :local isDisabled [/ip firewall mangle get [:pick $mangleID 0] disabled]
    :if ($isDisabled = false) do={
        :put "[SUCCESS] Mangle Rule 'TOGGLE_INTERNET_HOTSPOT' is ENABLED."
    } else={
        :put "[ERROR] Mangle Rule is still DISABLED! Check Hotspot connection."
    }
} else={
    :put "[ERROR] Mangle Rule 'TOGGLE_INTERNET_HOTSPOT' not found!"
}

:local bridgeComment [/interface bridge get [find name="bridge-LAN"] comment]
:put ("[+] Bridge Comment: " . $bridgeComment)

:put "============================================="
:put "   TEST COMPLETED. CHECK ROUTER LOGS!        "
:put "============================================="