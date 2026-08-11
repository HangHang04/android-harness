# Wireless and USB connection recovery

Use this reference only when `doctor` reports an absent, unauthorized, offline, locked, or ambiguous device.

## Preserve the trust boundary

- Let the user unlock the phone, approve RSA trust, enable wireless debugging, and enter pairing codes locally.
- Never request, repeat, log, or store a six-digit pairing code. If one is exposed, have the user close the dialog and generate a new code.
- Do not disable VPN, firewall, endpoint protection, or USB security settings without the user's approval.
- Do not scan broad port ranges. Use only the current pairing or connection port shown by Android or advertised by ADB mDNS.

## Diagnose USB before changing drivers

Run `adb devices -l`, then inspect Windows for present WPD, MTP, or Android ADB interfaces. An `unauthorized` row means the data path works and the user must approve the RSA prompt.

Windows Device Manager error 43 with **device descriptor request failed** occurs before ADB authorization. Treat it as a USB data-link problem: ask the user to try a direct USB port, a known data cable, and an unlocked phone. A selected "File transfer" default is not proof that Windows has enumerated the phone.

## Pair over a Windows mobile hotspot

A Windows PC can share Ethernet through a Wi-Fi mobile hotspot. The PC is the hotspot gateway; the phone connects to that Wi-Fi network. Android 11+ can then use **Developer options > Wireless debugging > Pair device with pairing code**.

Pairing and connection use different, short-lived ports:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb pair 'PHONE_WIFI_IP:CURRENT_PAIRING_PORT'
& $adb mdns services
& $adb devices -l
```

The user must type the pairing code at the prompt.

## Correct a virtual or VPN address shown by Android

Some phones display a VPN or acceleration-interface address instead of the Wi-Fi address on the wireless-debugging page. Suspect this when the displayed address is outside the hotspot subnet or routes to another local interface.

1. Identify the hotspot gateway and connected client without printing MAC addresses:

```powershell
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object InterfaceAlias -Match 'Local Area Connection|Wi-Fi Direct|移动热点' |
    Select-Object InterfaceAlias, IPAddress, PrefixLength

Get-NetNeighbor -AddressFamily IPv4 |
    Where-Object State -NotIn 'Unreachable', 'Incomplete' |
    Select-Object InterfaceAlias, IPAddress, State
```

2. Select only the phone candidate in the hotspot subnet. Do not guess when multiple clients are present.
3. Keep Android's current pairing port but substitute the verified Wi-Fi IP.
4. Optionally verify that exact endpoint before pairing:

```powershell
Test-NetConnection -ComputerName 'PHONE_WIFI_IP' -Port CURRENT_PAIRING_PORT
```

5. Pair with a newly generated code. After success, let ADB mDNS discover the separate connection port. If discovery stalls, restart only the local ADB server and recheck:

```powershell
& $adb kill-server
& $adb start-server
& $adb mdns services
& $adb devices -l
```

Run `android-harness --json doctor` again before any phone action.
