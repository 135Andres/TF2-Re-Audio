# Security review and next-step plan

Date: 2026-10-15. Status: S1 implemented and SEC-04 destination allowlist implemented 2026-10-16 (see S1/S4 checkboxes); S2, S3, S5, S6 and the rest of S4 unstarted.
Requested next human session: native Windows on 2026-10-16.

**Goal:** protect users' computers, credentials, recordings and ability to use the local app when sharing with friends or playing TF2. Keep the existing invitation workflow.
**Architecture:** local browser controls, a separate optional sync listener, an outbound tunnel and a local RCON client. Treat every network message as untrusted, including messages from group members.
**Constraints:** Python >=3.10, standard library only, Windows/Linux, pathlib, English product/documentation text, persistent writes through util.atomic_write. Source ownership remains as defined in TASKS.md. Any future change spans explicit owner handoffs; this document assigns work but implements none.
**Inputs:** PLAN.md, TASKS.md, collaboration-design.md and collaboration-report.md. This plan supplements the previous functional implementation; passing those functional checks was not security acceptance.

## 1. Exposure model

| Surface | Current implementation | What must be verified |
|---|---|---|
| Browser control API | server.py binds 127.0.0.1; Host/Origin/write-header checks; CSP; no remote UI listener | Actual process/listener addresses on Windows and Linux, IPv6 behavior and protection against malicious websites |
| Group sync | sync.py binds a separate 127.0.0.1 TCP port | Only the sync API is reachable through the tunnel; no browser controls, filesystem listing, RCON, settings or downloads |
| Cloudflare tunnel | cloudflared receives the dedicated sync port, started only through hosting controls | Outbound connector, correct destination port, shutdown and failure behavior; publicly reachable sync is still an attack surface |
| TF2 RCON | rcon.py connects to 127.0.0.1; generated launch options request +ip 127.0.0.1 | The real TF2 process actually binds RCON to loopback under all supplied launch options; outgoing client address alone does not prove this |
| TF2 gameplay | A separate game connection managed by TF2 | Observe before/during/after Casual. Do not infer app or RCON reachability from a gameplay connection or shared port number |
| Disk/runtime | JSON, validated WAV, derived MP3, ZIP backups, Python and cloudflared executables | Containment, ACLs, junctions/symlinks, authentic builds, current runtime patches, no secrets in logs/artifacts |

The app does not read commands or take files from a TF2 match server for synchronization. Source inspection establishes the intended separation; it does not prove that the native game or network environment has no vulnerabilities. Lack of a public user list or an obscure tunnel URL is not an access control.

Cloudflare documents an outbound connector model: no router port forwarding is required for this design. Requests can still reach the published sync service through that connector. The tunnel is not a substitute for authentication, input validation or resource limits. [Cloudflare Tunnel architecture](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/).

## 2. Attacker and trust boundaries

Cover anonymous visitors who know the tunnel URL, malicious/compromised invited members, a removed member using stale credentials, malicious websites contacting localhost, hostile host links, malformed audio/snapshots, local accounts reading weakly protected secrets, and compromised runtime distributions.

The current protocol trusts the selected host with group history and bearer credentials. A group_id returned by hello is public identification, not cryptographic proof of the host. A SHA-256 audio hash detects changed bytes, not the identity or honesty of the author. HTTPS authenticates the URL's TLS endpoint; it does not certify that it is the intended friend's host.

A fully compromised OS or another process already running as the same user is outside the protection this app can promise. Tests still need to check ordinary cross-account file permissions and accidental secret disclosure. Never claim immunity to hacking or VAC approval.

## 3. Findings and evidence

| ID / priority | Finding | Evidence and impact |
|---|---|---|
| SEC-01 / P0 before internet hosting | Incomplete unauthenticated invite requests hold the application lock | Reproduced with a temporary GroupStore, loopback port 0, the shared lock and one partial redeem body. The lock was unavailable while the body was read. sync.py _run holds owner._lock around _body; server.py supplies its UI lock. Demonstrated availability issue, not demonstrated code execution |
| SEC-02 / P0 | Connections/threads and request lifetimes have no explicit total bound | Static inspection: ThreadingHTTPServer plus per-socket inactivity timeout. A timeout between reads does not define an absolute request deadline. Needs a small bounded slow-client test; no load attack was run |
| SEC-03 / P0 | Per-file limits do not bound total work, disk or buffered audio | Static inspection: server POST and client pull collect audio in staged dictionaries; collection history is retained, inbox quota is per member. No total group/round budget or group-wide staging quota. A permitted member or host can consume resources with valid files |
| SEC-04 / P1 before accepting untrusted links | Host validation accepts internal HTTPS destinations | Validator-only reproduction accepted https://127.0.0.1:8443, https://[::1] and https://169.254.169.254. No connections to those addresses were made. This proves a destination-policy gap, not a completed SSRF exploit; TLS and subsequent protocol checks still apply |
| SEC-05 / P1 | Host replacement relies on a trusted link and public group_id | Static inspection: check_host verifies version/group_id before the saved bearer token is sent. A hostile accepted endpoint can claim a known group_id. Need an explicit host-trust and credential policy; current host trust must be disclosed |
| SEC-06 / P1 | Secret recovery, permission checks and revocation lifecycle need native validation | Tokens are excluded from snapshots and normal UI status; plaintext local bearer tokens and RCON passwords are necessarily sensitive. Native Windows ACLs, backups, clipboard and stale-host behavior remain untested |
| SEC-07 / P0 runtime review | Windows fallback still pins Python 3.12.10 | Source: TF2ReAudio.cmd. A correct hash identifies the pinned artifact but does not make an old runtime patched. Python documents later 3.12 security releases; review affected modules and select a maintained Windows binary before security acceptance |
| SEC-08 / P1 | Peer disconnect during an error response can print a traceback | Observed BrokenPipeError in the temporary partial-request fixture when it closed. Error writing from an exception handler escapes the handler. No credential disclosure was observed; expected disconnects should remain quiet |

Sources for the runtime concern: [Python 3.12.10](https://www.python.org/downloads/release/python-31210/), [later security-only 3.12 release](https://www.python.org/downloads/release/python-31211/). This review does not assert a specific exploitable CVE in this application's use of that runtime.

Positive controls already present: loopback-only Python listeners, separate UI/sync ports, bearer authentication, invitation expiry/single use, immutable ID checks, catalog validation, WAV/hash checks, no new client pruning declarations, blocked redirects, manual apply, local-only RCON client, atomic writes, pinned executable hashes and safe text rendering. Keep their regression tests; none is a complete security assessment by itself.

Python explicitly cautions that http.server provides limited hardening for production use. Under the standard-library constraint, external hosting needs explicit admission control and adversarial acceptance, not just a tunnel around the current listener. Untrusted JSON can also consume CPU/memory. [HTTP server guidance](https://docs.python.org/3.12/library/http.server.html), [JSON guidance](https://docs.python.org/3.12/library/json.html).

## 4. Approach and ordering

Recommended: retain the existing friends/invitation design, complete P0 transport/resource/runtime work first, then host-link/credential and content-boundary work. Keep hosting off for tomorrow's initial solo Windows checks. A narrowly scoped, supervised network test can follow the P0 fixes; broader internet use waits for the matrix below.

Alternatives: postponing collaboration entirely leaves solo Windows testing available with less network surface; a redesigned hosted service or audited signature-based protocol could reduce host trust but adds scope/dependencies. Do not invent custom cryptography to satisfy the standard-library constraint. Malicious-host provenance protection needs a separate design decision before any promise of that protection.

Proposed starting limits for future implementation: 8 admitted sync connections, queue of 8, 5-second absolute header deadline, 20-second absolute body deadline, 25-second whole-request deadline; 16 MiB JSON/request and existing MAX_BYTES/audio; 16 MiB staged audio per member, 64 MiB globally, 512 MiB unique committed group audio and 32 active members. These are proposed budgets to validate against friend-group use and Windows performance, not existing enforced limits. Returning a bounded error and preserving the saved recording is preferable to bypassing the budget. Deadline accounting must include work/lock waiting, not only socket inactivity.

Keep audio buffering to one validated blob at a time. Apply a 16 MiB download budget per sync round, with persistent bounded staging and continuation on later rounds; never partially publish a snapshot that requires unavailable audio. Protect collection and backup references from cleanup, and count unique hashes consistently. Proposed staging TTL: 24 hours for unreferenced incomplete data; expiration must not remove active, conflict or backup data.

## 5. Future implementation tasks — all unstarted

### S1 — Separate request admission/read from state commit (P0)

**Owners/files:** T12 sync.py/tests/test_sync.py; T14 server.py/tests/test_server.py; T13 tests/test_integration_sync.py.
**Interfaces to agree:** SyncServer's admission/deadline policy; keep its existing mutation lock only for short validated state changes. Syncer cancellation must interrupt pending network work without a post-stop commit.

- [x] Reproduce SEC-01 as a fixture regression: hold one incomplete redeem body; /api/state must complete within 2 seconds on an otherwise idle fixture host.
- [x] Bound admitted handlers before spawning worker threads; reject overflow with a small 503 response or close safely without taking the app lock.
- [x] Enforce absolute header/body/total deadlines; test a peer that supplies data often enough to avoid an inactivity timeout.
- [x] Read/parse outside the app lock; recheck membership/invite validity at commit to avoid authorization races.
- [x] Verify invalid token, malformed length, duplicate headers, chunked input and disconnected error writes do not hang or print tracebacks; no secrets in errors.
- [ ] Verify loopback-only binding, local Origin/Host checks and sync endpoint allowlist, including RCON/settings/static/download paths; reject any future wildcard bind by default.

Done in sync.py (tests/test_sync.py): 8-slot admission with 503 overflow, 5/20/25 s absolute deadlines via a per-connection watchdog (the header deadline covers header lines, not only the request line), lock waits bounded by the request deadline (503 busy), body read and WAV/hash checks outside the app lock with token recheck at commit, responses written after the lock is released, quiet peer disconnects (SEC-08), chunked/duplicate/malformed Content-Length and unauthenticated write regressions. Not yet: Windows run. The endpoint allowlist item is covered by existing tests for /, settings and downloads; there is no wildcard bind option to reject.

**Acceptance:** capped handlers/memory, responsive local UI under eight slow fixture peers, automatic cleanup after deadline, existing functional tests green.

### S2 — Aggregate resource budgets and atomic ingestion (P0)

**Owners/files:** T12 sync.py/tests/test_sync.py; T8 store.py/tests/test_store.py and a supported ingestion API; T11 group.py/tests/test_group.py for membership limits; T13 integration tests. No owner files changed in this planning turn.
**Interface to design first:** public Store transaction/staging API that accepts validated metadata and references to validated staged files, with rollback/recovery. Replace the current private-hook/blob-layout adapter through T8's owner.

- [ ] Make quota accounting unique-hash based, global as well as per member, and durable across restarts; reject the quota-crossing write before committing metadata.
- [ ] Stream each blob to bounded staging rather than holding the full audio set in memory; enforce round/download/group limits and remaining disk reserve.
- [ ] Preserve staging between bounded rounds without publishing missing audio, acknowledge only committed records, and clean stale unreferenced inbox data safely.
- [ ] Reject excessive nesting, duplicate JSON keys, unknown schema fields where appropriate, oversized strings/event edges and pathological event counts before expensive merge work.
- [ ] Test exhaustion with small fixture limits, not real memory/disk exhaustion. Include disk/write failures, duplicate uploads, cancellation and restart halfway through commit.

**Acceptance:** valid but oversized groups/requests cannot consume unbounded resources; saved/active/conflict/backup recordings survive all rejected attempts.

### S3 — Review executable trust and runtime patch policy (P0)

**Owners/files:** T6 launchers/docs/launchers.md; T7 tunnel.py/tests/test_tunnel.py; T19 build tool/tests/user guide; T10 doctor output.

- [ ] Inventory the actual selected Python, SSL and cloudflared versions; compare official security releases against used modules. Document affected and unaffected advisories rather than guessing CVEs.
- [ ] Select a maintained official Windows embeddable runtime and freshly verified SHA-256, then test extraction/runtime paths and startup. Do not replace executable pins during this planning turn.
- [ ] Distinguish language compatibility (>=3.10) from a security-supported patch level. Define minimum patch versions per supported branch at implementation time; do not silently prefer an old system Python over the reviewed runtime.
- [ ] Keep hash-before-execution and canonical HTTPS downloads, bounded download sizes, safe extraction and no shell-interpolated untrusted values. Review a tampered cached binary and interrupted bootstrap using fixtures.

**Acceptance:** an identified candidate uses a reviewed runtime, wrong hashes prevent execution, no package includes data/secrets, and normal launch requires no administrator rights.

### S4 — Constrain destinations and host changes (P1)

**Owners/files:** T11 group.py/tests/test_group.py; T12 sync.py/tests/test_sync.py; T14 server.py/tests/test_server.py; T18 group.js; T15 strings.js/tests/test_web.py.

- [x] For the initial supported tunnel mode, allow only a normalized HTTPS quick-tunnel hostname on port 443; exclude the provider API hostname, credentials, query/fragment, IP literals, deceptive suffixes and alternate ports. Keep loopback HTTP as an explicit fixture/developer policy, not a normal join default.
- [ ] Reject non-public DNS results before connection and verify the address actually used, preserving TLS hostname verification. A one-time DNS lookup followed by independent urllib resolution is insufficient against rebinding. Test with a fake resolver/transport; never probe real internal services.
- [ ] Keep redirect rejection for both unauthenticated and credential-bearing requests. Define proxy behavior explicitly instead of accidentally inheriting a proxy that bypasses destination checks.
- [ ] Show the full normalized new host origin before updating; never regard hello/group_id as proof. Define how trusted host changes are approved and how credential rotation/revocation works without breaking offline recovery.
- [ ] Document the remaining trusted-host model. A hostname restriction alone cannot authenticate a friend; a malicious quick-tunnel endpoint remains possible.

Done in group.validate_url (tests/test_group.py, tests/test_sync.py): only https://<label>.trycloudflare.com on port 443 (not api.), normalized to the origin, or http://127.0.0.1:<port>. Blocked links make zero requests. Loopback HTTP is still always allowed (marked shortcut in code). DNS checks are not added: the allowlisted names resolve through Cloudflare's DNS, not attacker DNS. System HTTPS proxies are still honored; decide whether to keep that.

**Acceptance:** blocked destinations cause zero network requests/credential transmission; wrong-group links preserve local state; approved host change tests pass with the residual trust model explicitly stated.

### S5 — Authorization, secrets and content boundaries (P1)

**Owners/files:** T11/T12/T13 for replicated permissions; T14/T15/T18 for local UI; T0/T8/T9 for file boundaries; T10 for grouped CLI behavior; owner-specific tests.

- [ ] Exercise a full permission matrix: anonymous, invalid token, member, admin, removed member, stale host. Test mixed-event batches, forged actors, replay, future Lamport values, concurrent admin changes and last-admin rules.
- [ ] Ensure an audio/snapshot/name can never select a shell command, arbitrary path or RCON command. Test MP3 output, WAV chunks, path traversal, symlinks and Windows junctions against disposable roots only.
- [ ] Audit CSP/CSRF/DNS rebinding, HTML injection and browser microphone lifecycle. Use hostile display names and snapshots in a real browser fixture.
- [ ] Verify tokens/passwords are absent from public responses, logs, doctor, exported collection and program ZIP; include .bak files and clipboard instructions in the review. Inspect Windows ACLs with a normal user; no blanket permission grants.
- [ ] Design invitation cancellation, credential rotation and re-invitation recovery without resurrecting removed identities. Revocation on isolated hosts remains delayed unless the trust/availability design changes.
- [ ] Before grouped CLI imports are supported, T10 must either reject them clearly or adopt GroupStore/member identity plus a shared process lock. Preserve the existing solo CLI path.

**Acceptance:** unauthorized operations and file escapes fail before commit; no network input reaches a general command interpreter; no secret exposure in the diagnostic/export matrix. A malicious host and same-user malware remain explicit limitations.

### S6 — Tunnel lifecycle and identified candidate (P1)

**Owners/files:** T7/T14 tunnel/server lifecycle and tests; T19 candidate build and user docs.

- [ ] Observe tunnel exit; stop serving the old public session and offer retry with a new link. Closing the app must stop all owned listeners and child processes.
- [ ] Separate safe diagnostics from raw cloudflared output; redact secrets/connection details from reports shared publicly.
- [ ] Freeze source and produce a new collaboration-enabled candidate with checksum and source manifest after approved fixes. Both testers must install that same candidate; do not use the old solo ZIP to claim collaboration acceptance.
- [ ] Run the focused adversarial matrix, full unittest suite and existing Chromium flows, then native Windows/LAN/tunnel tests using the separate checklist.

**Acceptance:** documented candidate identity, completed P0 checks, explicit remaining risks, no release/security claims based only on a green functional suite.

## 6. Tomorrow's session and later release gate

Use [Windows security checklist](windows-security-checklist.md) alongside milestone-wave2.md and the existing Windows sheet. Start with solo mode, identify listeners/processes and inspect actual TF2 RCON binding. Never fix a failure by forwarding 27015/8440, disabling the firewall or granting administrator rights to the app. A gameplay UDP endpoint must be interpreted separately from RCON TCP.

All P0 fixes are unimplemented at the end of this turn. Keep internet hosting off for baseline Windows validation. Record unavailable checks as Not run; local functional acceptance can progress separately. Real group hosting acceptance follows the identified P0-fixed candidate and an explicit supervised test session.

Before wider distribution: all P0 items closed with regression evidence; destination/credential policy settled; Windows actual bindings and LAN rejection observed; malformed/slow requests tested; packaging free of secrets; both people using the same build. This is a practical release gate, not a guarantee of absence of vulnerabilities.

## 7. Work performed and limits of this review

Read current source and task contracts; consulted primary Python, Cloudflare and Microsoft documentation. Ran one bounded loopback partial-invite diagnostic and three validator-only URL checks using disposable roots. The partial request also exposed the BrokenPipe console traceback. No real TF2, real data, real tunnel, firewall changes, internal-network probes, downloads, exploit deployment or load test was used.

Application source, launchers and tests are unchanged by this turn; documentation is updated only. No new security tests or fixes have been implemented, and the earlier 238-test result belongs to the previous functional implementation. Native Windows/real network acceptance remains pending. The task/file owner requests above are the implementation handoff.
