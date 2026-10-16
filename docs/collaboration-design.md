# Collaboration design

Approved direction: docs/collaboration-ideation.md and the user's request to apply it.
Implementation authorization supersedes the earlier Wave 2 sequencing gate; native Windows and TF2 acceptance remain pending.

## Scope and trust
One active group per installation. Python >=3.10, standard library only. All persistent writes use util.atomic_write. User-visible copy is English. Implement task ownership in order: T11, T12, T13, T14 delivery 2, T18 plus its T15 shell/string integration. Do not modify T8 or unrelated work.

Hosts are trusted replicas. HTTPS authenticates the chosen host; this protocol does not cryptographically authenticate historical records against a malicious host. Clients may upload their own new records and exact echoes of known records. A replacement host should synchronize all history before takeover. Offline takeover is allowed from its saved replica; missing audio blocks hosting, and the UI warns that only saved history is available. Revocation is effective after the host learns it. Membership changes use a validated Lamport event log; removals cannot be undone by stale promotions. Last-admin removal is blocked locally.

## Group
Group.create(name, my_display_name, *, root=None, device_id=None) persists group.json; Group.load(root), Group.join(snapshot, member_id, token, device_id, root), snapshot(), merge(snapshot, actor=None) support replication. Local credentials and host URLs never enter snapshots. Admin operations use the local identity. Tokens are random 32-byte secrets; replicas retain SHA-256 hashes and verify with compare_digest. Invitations are single use with 24-hour default expiry. GroupError covers expected errors. Backup recovery preserves damaged files when both copies fail.

## Sync
A separate loopback HTTP listener serves hello, redeem, snapshot and hashed blobs, never local UI/settings. Public downloads stay disabled. Requests carry protocol version; unknown versions get 426. Bound JSON to 16 MiB / 50,000 records and audio to MAX_BYTES. Reject chunked/ambiguous lengths, invalid WAV/hash/catalog lines, changed immutable IDs and unauthorized new records. Redeem is limited to five attempts per minute per socket IP; proxy headers are ignored (conservative shared bucket behind a tunnel).

Snapshot envelope: protocol_version, group_id, group, collection. GET uses ETag, POST accepts echoes plus owned deltas and returns acknowledged record IDs. Pull validates and stages all required audio before merging collection metadata; push uploads validated blobs before metadata. Failed attempts preserve pending sharing. 304 does not suppress outgoing work. Retry interrupted audio from byte zero. Syncer polls every 15 seconds with bounded backoff to 120 seconds and statuses synced, host_offline, auth_failed, update_required. No sync path calls game.apply or sync_files. Local UI pending-apply status includes received metadata so manual Apply is visible even before installation.

GroupStore, a T12 adapter over Store's existing commit/state hooks, preserves all shared takes until T8 provides safe replicated retention. Grouped clients may only echo pruning records already known to the host; new client tombstones are rejected regardless of role. Legacy solo events whose audio was already pruned remain local history, are omitted from outgoing sharing and excluded from grouped pending counts. Solo retention is unchanged. This trades bounded history growth (the sync request/record limits still apply) for protection from accidental or forged deletion. The T8 owner should replace the private-hook adapter with a supported public contract.

## Joining and UI
Joining requires explicit consent to share existing recordings. Export a recoverable solo ZIP first; retain original immutable solo records and bind the joining device's legacy local author during sync validation. Existing foreign history imported from ZIP must be rejected for sharing rather than relabeled. Validate group identity on Update link. UI includes create/join, consent, invite copy fallback, member promote/remove, suggested voices, host toggle and status. UI remains usable offline; networking is started only for a joined group. Group deletion/switching is outside this version. Disable destructive collection reset/import while grouped until migration semantics exist.

## Acceptance
Use unittest with temporary roots, fixture catalog/WAVs, fake clocks/tunnels and loopback port 0. Verify invitations, expiry/reuse, roles, recovery; HTTP authentication/version/ETag/limits, validation/forgery rejection; three-device offline conflict, stale restore, host change, revocation and interrupted retry; local API integration and browser group flow if Chromium is available. Run the full suite. Do not claim Windows, physical microphone, real tunnel or TF2 acceptance.

## Accepted limitations and owner handoffs
No malicious-host provenance proof, multi-group switching, group leaving/re-invitation recovery UI, public downloads or byte-range resumption. A lost/revoked local credential currently requires data-folder recovery, not an in-app re-invitation flow. The existing solo CLI import path is not group-aware; use browser recording while grouped. T10 must adopt GroupStore and the member identity before grouped CLI imports are supported. T19 must rebuild the candidate after integration. Native Windows, real internet tunnel and TF2 acceptance remain separate checks.
