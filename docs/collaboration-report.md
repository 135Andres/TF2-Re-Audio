# Collaboration implementation report — 2026-10-15

## Delivered

Implemented the approved ideation in the shared working tree. The user's follow-up authorizes collaboration development ahead of the previous sequencing gate; Windows/TF2 acceptance remains open. No commit, publication or real tunnel launch was performed.

- T11: group identity, local bearer credential, replicated token hashes, Lamport membership events, single-use expiring invitations, admin/member permissions, promotion, revocation, suggested voices, host links, version checks, atomic persistence and backup recovery.
- T12: separate loopback sync HTTP listener (never local UI/settings), protocol negotiation, authorization, ETags, bounded requests, invitation rate limiting, hash/WAV/catalog validation, immutable record checks, staged audio, acknowledgments, client retries and background polling/backoff. Redirects never receive bearer credentials. Proxy IP headers are ignored deliberately; a tunnel uses a conservative shared invitation bucket.
- T13: three-device offline exchange/conflicts/resolution, original restoration against stale state, host replacement preserving identity, propagated revocation, restart recovery, interrupted transfer and lost acknowledgment retry.
- T14 delivery 2: local group API, explicit existing-recording consent and backup, member identity for browser recordings, worker/host/tunnel lifecycle, manual apply visibility for received metadata and protection against importing/deleting a grouped collection. CLI `host` opens local group controls; hosting is enabled explicitly in the browser.
- T18 with T15 shell integration: Group dialog, create/join/invite, copy fallback, status, member management, suggested voices, host toggle, Update link and Sync now. English strings, safe text rendering, keyboard close/focus restoration, existing visual style and responsive form controls.

## Important design choices

Hosts are trusted replicas. This is not cryptographic provenance protection against a malicious host. Replacement hosts should synchronize first; offline takeover exposes only the saved replica. Revocation applies after a host learns it and never deletes audio already copied to a removed member.

GroupStore in T12 uses the existing Store commit/state hooks to retain all shared takes. Solo retention is unchanged. A member cannot submit new pruning tombstones, including unknown IDs that could suppress another member's later upload. Previously pruned solo history is kept locally but omitted from sharing and from grouped pending accounting. This conservative policy takes priority over automatic shared retention until T8 offers a supported safe contract.

Interrupted WAVs restart from byte zero, rather than byte-range resumption. Audio and metadata are verified before metadata commit. Failed attempts leave the outgoing queue retryable; a lost acknowledgment is idempotent. A 304 response does not suppress outgoing changes. No sync path installs game files or sends snd_restart.

## Validation

Baseline: `python -m unittest` ran 211 tests, OK, 13 skipped before implementation.

Targeted final group/sync/integration/server run: 49 tests, OK. Additional regressions cover grouped retention of eleven recordings, existing solo pruning, forged active/unknown tombstones, wrong group, foreign authors/admin events, pending apply before installation, wire-level partial audio and acknowledgment loss.

Chromium checks cover creating a group, generating an invitation, safe display names, Escape/focus restoration, joining another fixture host, downloading audio and showing manual Apply without creating the game mod directory. The create/focus check initially failed intermittently because the assertion raced the native dialog close event; it now waits for the required focus result and repeated targeted runs pass.

Full final suite command:

```sh
TF2RA_PLAYWRIGHT=/home/lav/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright \
TF2RA_BROWSER=/home/lav/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome \
python -m unittest
```

Final full suite: 238 tests in 103.850 seconds, OK, 2 skipped with Chromium enabled. The existing duplicate-name ZIP fixture warning is expected. The two network/manual tests remain skipped.

`python -m unittest tests.test_build_zip`: 2 tests, OK. `git diff --check` and Node syntax checks pass. A Linux Chromium screenshot of the group panel was visually inspected; hosting controls were moved before the long suggested-voice list.

Independent read-only review found retention blocking sync and forged-pruning deletion. Regression tests reproduced both before fixes; a second review confirmed those fixes and found the legacy pending-state issue, also reproduced and fixed. No other task's Store source was modified. Existing changes in tests/test_game.py and concurrent UI work were preserved.

## Not tested / not delivered

- Native Windows, physical microphones, real TF2 playback or Casual snd_restart latency.
- Real internet synchronization, a live cloudflared process/download, firewall/antivirus behavior, or recovery from a dying tunnel process. If a live tunnel dies, restart the app before hosting again.
- Firefox, screen readers, a complete WCAG audit or the five-person usability study.
- Malicious-host protection, immediate revocation on isolated hosts, multi-group switching, in-app leave/re-invitation recovery, public downloads or automatic game apply.
- Hardware power-loss durability or actual disk exhaustion. Group persistence tests inject write errors.
- Group-aware CLI import. Use browser recording while grouped: the legacy solo CLI still uses ordinary Store retention and is not a supported group editing path.
- The candidate ZIP was not regenerated or published.

## Owner requests and useful follow-ups

1. T8: provide public APIs for validated audio staging plus metadata commit, configurable shared-history retention, pending/shareable record accounting and a provenance-aware pruning contract. The current T12 adapter intentionally uses existing private validation/commit/state hooks and the documented blob layout instead of editing T8 files.
2. T10: route CLI import through GroupStore and the group member identity; prevent simultaneous CLI/browser writers before supporting grouped CLI edits.
3. T7/T14: detect a dead tunnel and offer restart without restarting the app; persist/display last complete sync so offline takeover can describe replica freshness more precisely.
4. T11/T18: add explicit leave/re-invitation/credential recovery and group migration before allowing switching or local group-data deletion.
5. T19: rebuild and identify a candidate ZIP containing these changes, then run the native Windows and real TF2/network acceptance protocols. Public distribution remains a separate decision.

Start using the implemented browser flow: Group → Create group → Host for the group → Share invite. A friend uses Group → Join a group with the host link and code. Each PC applies received changes manually.
