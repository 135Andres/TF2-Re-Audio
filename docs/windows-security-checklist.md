# Native Windows security checklist — 2026-10-16 session

Status: prepared on Linux, all native checks **Not run**. This supplements milestone-wave2.md and agent-reports/04-windows-validation.md. It does not replace physical microphone, audible TF2 or Casual tests.

Both participants must have TF2 Re-Audio and TF2 installed. Each must run the same identified collaboration-enabled build to test groups. The current old candidate may only contain solo use; record that limitation instead of marking group tests passed.

## 1. Identify the test candidate

Record date/time, Windows version from winver, browser version, source commit plus included changes, ZIP name, expected/observed SHA-256 and the interpreter actually selected by the launcher. Do not attach launch options, process command lines, group.json, settings.json, raw invites or tokens to reports.

Read-only PowerShell examples (replace the ZIP path):

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\path\TF2ReAudio-candidate.zip'
Get-Process | Where-Object { $_.ProcessName -match '^(python|pythonw|tf_win64|hl2|cloudflared)' } | Select-Object Id, ProcessName
Get-NetTCPConnection -State Listen | Select-Object LocalAddress, LocalPort, OwningProcess
Get-NetUDPEndpoint | Select-Object LocalAddress, LocalPort, OwningProcess
```

Use OwningProcess to match each row to the app, TF2 and cloudflared; do not assume that every Python process belongs to this test. LocalAddress 0.0.0.0 means all IPv4 interfaces; :: means an IPv6 wildcard requiring separate interpretation. Expected app/sync bindings are 127.0.0.1, with no wildcard or LAN listener. Record the actual local UI port (8440 is only the default) and sync port (dynamically selected).

Microsoft documents these listener fields: [Get-NetTCPConnection](https://learn.microsoft.com/en-us/powershell/module/nettcpip/get-nettcpconnection), [Get-NetUDPEndpoint](https://learn.microsoft.com/en-us/powershell/module/nettcpip/get-netudpendpoint). Commands may require permission to see all processes; record access failures rather than running the app as administrator.

## 2. Baseline solo checks — run first

| ID | Check | Expected / stop rule | Result |
|---|---|---|---|
| WS01 | Launch solo as a normal user with TF2 closed | UI on loopback only; no cloudflared and no sync listener | Not run |
| WS02 | Open TF2 with the generated local RCON options | Identify its TCP listener by PID and configured port; it must be loopback before optional RCON is accepted | Not run |
| WS03 | Repeat listener inventory while in Casual, then after leaving | Distinguish gameplay UDP/outbound connections from RCON TCP. Any unexpected RCON wildcard/LAN binding fails this check | Not run |
| WS04 | From the other consenting test PC on the same LAN, try the known UI and RCON TCP ports | Both direct connections fail while local browser/RCON still work. Do not test arbitrary hosts/ports | Not run |
| WS05 | Review existing inbound firewall rules for the exact app/TF2 executable and ports | No rule added by this test to expose Python/UI/RCON. Do not alter unrelated Steam/TF2 rules or disable Defender | Not run |
| WS06 | Inspect data-folder ACLs without sharing file contents | Another normal account should not read tokens/RCON secrets/backups. Record inherited grants; do not broaden permissions | Not run |
| WS07 | Create a doctor report and collection export; inspect locally for secrets | No passwords, bearer tokens or invites. Keep the private report private if a secret is found | Not run |
| WS08 | Close app/TF2 and repeat inventory | App-owned listeners/processes disappear; other processes are not terminated | Not run |

For WS04 use only the two test PCs and known recorded ports:

```powershell
Test-NetConnection -ComputerName 'TEST-PC-LAN-IP' -Port UI-PORT
Test-NetConnection -ComputerName 'TEST-PC-LAN-IP' -Port RCON-PORT
```

Replace the placeholders with the tester's LAN address and numeric ports; these two template lines are not ready-to-paste commands. A failed LAN connection alone does not prove loopback binding: WS01–03 must also pass. Router port forwarding and UPnP changes are unnecessary and must not be used to make this test work.

If WS02/03 finds exposed RCON, stop optional RCON testing, close TF2 and remove only this app's RCON launch options. Continue solo testing by restarting TF2 to load saved voices; report the exact binding and options ordering with the password redacted. Do not test live remote RCON authentication against an exposed game.

Read-only rule/ACL inspection examples:

```powershell
Get-NetFirewallRule -Enabled True -Direction Inbound | Select-Object DisplayName, Action, Profile
icacls "$env:APPDATA\TF2ReAudio"
```

Correlate firewall rules with their application/port filters before drawing conclusions; the displayed names alone are not evidence of an allow rule's scope. [Microsoft firewall-rule reference](https://learn.microsoft.com/en-us/powershell/module/netsecurity/get-netfirewallrule).

## 3. Supervised group checks — pending P0 hardening

Do not enable internet hosting on the current unhardened preview for baseline Windows acceptance. After S1–S3 are implemented and the candidate identified, the two testers can run:

| ID | Check | Expected | Result |
|---|---|---|---|
| WG01 | Compare candidate checksums on both PCs | Same collaboration-enabled build and compatible protocol | Not run |
| WG02 | Host on; inventory listeners and child process | Dedicated sync loopback listener plus outbound cloudflared; UI/RCON remain private | Not run |
| WG03 | Invite the second installed app and exchange one recording | Explicit join consent; received audio waits for manual Apply | Not run |
| WG04 | Without credentials request hello, snapshot, blob, settings and UI through the tunnel | Only documented public hello/redemption routes; protected data denied; UI/settings/RCON never served | Not run |
| WG05 | Reuse/expire an invite; remove the second member | Used/expired invites rejected; updated host rejects removed member; no claim that downloaded copies were erased | Not run |
| WG06 | Stop hosting, restart hosting, close app, simulate connector exit | Old endpoint/listener shuts down; fresh link shown when appropriate; no orphan owned process | Not run |
| WG07 | Repeat direct LAN checks for UI/sync/RCON | Still inaccessible directly; sharing works through the approved tunnel | Not run |

Slow-client, quota, malformed-WAV and forged-record tests belong in disposable automated fixtures first. Do not run availability stress tests while a friend is playing.

## 4. Record and clean up

For every row record Pass / Fail / Not run, candidate hash, process/PID, local address, port/protocol, timestamp and redacted evidence. Capture socket inventories rather than screenshots of launch options. Restore previous voice selections, remove only test-specific options if desired, stop hosting and confirm shutdown. Leave Windows firewall and the user's existing TF2/network configuration intact.
