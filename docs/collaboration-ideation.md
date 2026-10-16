# Wave 3 collaboration — initial ideation

Date: 2026-10-15. Status: proposal for discussion, not an implementation contract.

This draft interprets the requested collaboration point as Wave 3 in PLAN.md, covering T11, T12, T13, T7 integration, T14 delivery 2 and T18. It does not change PLAN.md or TASKS.md, complete the Wave 2 milestone, or enable network services. Implementation remains subject to the existing milestone gate.

## Product idea

A group of friends builds one shared voice collection. Everyone can record while offline. When a host is available, saved recordings travel to the group. Each person chooses when to apply received changes to TF2. Hosting provides connectivity; admin status provides membership permissions.

The first successful session should be: A creates a group, invites B, B records MEDIC!, A receives and previews it, and A manually applies it. The next demonstration adds C and an offline conflict.

## Proposed first version

- One active group per installation. Multiple groups and accounts stay outside this first slice.
- A member manually enables hosting. Another member can take over using a new link; no automatic host election or discovery.
- Joining uses a host link, a single-use invitation and a display name. Sharing an invitation copies the link and code together.
- Saved takes and line history are shared after joining; an explicit joining summary explains the scope. Unsaved previews, local original overrides, TF2 paths and RCON settings stay local.
- Received recordings remain pending manual application. Sync never silently reloads game audio.
- Concurrent recordings remain available for preview and explicit resolution. The deterministic winner is a temporary selection, not evidence that someone approved it.
- Member roles and suggested voices remain in scope as specified in T11/T18, after the recording exchange works. Suggested voice is guidance, not an exclusive recording permission.
- Public app downloads remain a separate distribution decision; a working host must not imply permission to publish a ZIP.

These are proposed defaults where the current contracts are silent, not newly approved requirements.

## User journeys

| Situation | Proposed experience | Success evidence |
|---|---|---|
| Create | Name group, choose display name, explain sharing, then offer hosting and an invite | Solo data survives; creator is admin |
| Join | Paste link and code, inspect group identity and sharing scope, then confirm | Membership and credentials commit successfully before background sync starts |
| Record offline | Save normally; show “Host offline — N recordings saved here” | Restarting the app preserves recordings and the outgoing queue |
| Reconnect | Retry automatically; display incoming changes and pending apply separately | Both devices can preview the same validated audio |
| Conflict | Show both recordings with author labels and preview controls; offer “Use this recording for the group” | Both takes survive; resolution converges |
| Host change | A synchronized member enables hosting and shares a new link; others use “Update link” | Link changes; group identity stays fixed |
| Removed member | Stop sharing and show a clear access message | Updated hosts reject the old token; local recordings remain available |

The proposed group panel has four areas: connection status, invite/join actions, members with roles, and hosting with a copyable link. Suggested voices belong beside the class cards. Status counts need explicit units: recordings awaiting sharing, lines awaiting application and unresolved conflicts must not be combined.

## Decisions to settle before coding

### 1. What happens to an existing solo collection?

The current store does not scope snapshots to a group. Silently merging a solo collection at join time could share recordings unexpectedly. Proposal: show the number of existing recordings and require an explicit choice about sharing them. Keep a recoverable local copy before any migration. Define how existing solo authors map to a new membership; do not rewrite immutable take IDs casually.

Leaving a group, switching groups and preserving a private collection need a concrete storage policy before offering those actions in the UI. One active group reduces scope but does not resolve this migration problem.

### 2. Who is allowed to introduce a replicated event?

T12 says uploaded takes and events must belong to the authenticated member. Existing Store takes include author_member_id and device_id; line events include device_id but no member identity. Full snapshots also contain other members' records, which must travel during host changes.

A token proves who sent a request; it does not by itself prove who originally authored every forwarded record. Proposal for the first protocol discussion: accept identical known records as echoes, bind newly introduced device records to authenticated membership, and explicitly design how another host accepts legitimate forwarded history. Do the same for admin events and pruning tombstones. A device-to-member map alone does not authenticate a forwarded claim.

This is an unresolved trust-model decision. Do not claim protection from forged forwarded history until a provenance rule and adversarial tests exist. Decide whether the initial trusted-friends model is sufficient or whether stronger provenance changes the scope.

### 3. Where do group state and credentials live?

T11 puts replicated group state in the store snapshot, but the current Store schema retains only defined collection fields. Proposal: discuss a versioned sync envelope containing group_id, protocol version, membership state and collection state. Local bearer credentials must remain outside that replicated envelope.

The client needs its original token on disk to reconnect; hashing tokens on the host does not eliminate local credential storage. Define the identity passed to each admin operation: the current Group signatures do not expose an acting member. Define recovery when group and collection persistence succeed at different times; separate atomic files are not one atomic transaction.

### 4. When has a recording actually been shared?

Proposal: acknowledge specific take/event IDs only after the host has persisted their metadata and validated required blobs. A timeout after host commit must be safe to retry. An ETag response of 304 is only evidence that the remote snapshot did not change; local pending changes may still need uploading.

Missing or invalid audio must not become ready to apply. Define the order of staging blobs, merging metadata and acknowledging records, including how garbage collection treats staged content. Bound snapshot size and record counts as well as individual WAV sizes.

### 5. What does interruption recovery mean?

PLAN.md describes resumable blobs, but T13 only requires the next sync attempt to finish. Proposal: for WAVs capped at 1 MB, first discuss restarting an interrupted blob from byte zero with bounded retries and no partial final file. Byte-range resumption would be a deliberate contract change or a separately specified feature; do not describe a full retry as byte resumption.

### 6. What does a host change preserve?

A new host can serve only the history and audio it actually holds. Proposal: display pending downloads before takeover and warn if the replica is incomplete. Validate group_id before accepting an updated link or modifying local state. Revocation takes effect at each host after it learns the removal; an isolated stale host cannot promise immediate revocation.

Resolve concurrent admin changes, expiry using wall time versus Lamport ordering, and last-admin removal rules explicitly. The plan already accepts concurrent redemption on disconnected hosts; preserve that documented limitation.

## Contract inconsistencies to resolve with owners

| Owner | Requested clarification/change |
|---|---|
| T11 | Define actor authorization, device/member association, local token storage, replica import/export, group schema version and concurrent membership rules |
| T12 | Define authenticated deltas versus forwarded records, acknowledgment semantics, envelope validation, request limits and interruption policy |
| T8 | Agree on solo/group migration, staged audio readiness, handling of conflicting content under the same immutable ID and authorized pruning; no Store edits made here |
| T13 | Extend scenarios with restart, lost acknowledgment, wrong group link, foreign-author injection, forged admin changes and partial persistence |
| T14 | Keep public sync on a separate listener from local UI; expose group status and manual apply without changing solo startup |
| T7/T12 | Define the trusted proxy boundary before trusting CF-Connecting-IP for rate limiting; direct clients must not choose their own trusted identity |
| T18/T15/T17 | Agree on join consent, offline/conflict presentation, strings and integration points owned outside group.js |
| Plan/T12 | Reconcile /api/redeem-invite versus /api/redeem, public hello exception, optional download policy and retry versus byte resumption |

Also clarify PLAN section 13.4: a joining client sends sync traffic even when its own hosting toggle is off. Privacy copy must describe both client sharing and hosting accurately.

## Proposed implementation sequence after the milestone

1. Settle the trust model, joining/migration behavior and versioned envelope; turn them into example requests and expected outcomes.
2. T11: persist identity/membership, invitations and roles with fake clocks and atomic-failure tests.
3. T12: exchange one recording between two temporary stores over loopback, with authentication and validation, without a tunnel.
4. T13: add C, offline edits, conflicts, restoration, host changes, revocation and interruption/restart cases. Require convergence across sync orderings.
5. Integrate T7 through T14, then add T18 and its local shell/setup integration. Keep manual apply.
6. Perform separate real-network and native Windows acceptance with identified builds. Automated loopback success is not that acceptance.

## Review and validation record

Done: reviewed PLAN.md and TASKS.md and inspected Store validation, snapshots, merge behavior, sharing flags and util.atomic_write. Produced this draft without changing implementation or another task's owned files.

Validation: checked this document's contents and repository diff. No executable behavior changed, so no test suite was run for this draft.

Not tested: Windows, real TF2, microphone, real synchronization, tunnel connectivity, hostile network traffic or any proposed UI flow. This is design work, not a claim of implementation readiness.

Changes needed from other tasks: the owner requests above must be resolved into contracts before implementation; they are proposals, not edits made by this draft.
