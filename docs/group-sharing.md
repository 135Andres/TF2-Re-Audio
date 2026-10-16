# Sharing recordings with friends — development preview

**Both people must install TF2 Re-Audio on their own PCs.** Every additional participant needs the app too. Each person also needs TF2 installed to hear the replacements in their own game. An invitation is a group link and code; it does not install the app, stream your microphone into the match or change other players' files.

Use the same collaboration-enabled build on both PCs. The collaboration code is currently in the development working tree; older ZIPs and repository downloads may contain only solo use. A matching version label alone is not enough for these preview builds: compare the supplied build checksum. Native Windows group acceptance is pending.

## Before sharing

The current security review found request/resource-hardening work that is still pending. Keep internet hosting off until the P0 work in the [security plan](security-next-steps.md) is completed and the candidate is identified. You can continue solo recording and perform the [Windows baseline checks](windows-security-checklist.md).

The workflow below describes the preview controls for a later supervised test. It is not a claim that the security work has already shipped.

## Host

1. Open your installed app and confirm your TF2 folder.
2. Open **Group → Invite friends → Create group**, enter a group name and your display name, and choose whether to share saved recordings/history. Existing recordings require explicit consent; a local backup is kept before joining/creating.
3. Enable **Start sharing**. This PC keeps sharing available while its app and tunnel are running. Hosting does not grant admin permissions.
4. Choose **Share invite → Copy invitation** and send the whole message privately to one friend. It contains a link to their local Join friends screen, a separate single-use code and fallback instructions. Invitations are available when hosting here or synced with the current host; this status is not a guarantee of continued availability. Keep the host app open.

## Friend

1. Install and open the same TF2 Re-Audio build on your PC; confirm your own TF2 folder.
2. Open the invitation link. It opens **Join friends** in your own running app and fills the host address; enter the separate invitation code and your display name if blank. Opening a link never joins automatically.
3. If the link does not open, go to **Group → Join friends → Have an invitation? Paste it here**, paste the whole message and choose **Use invitation**. The link targets the default local port 8440; pasting works when your app uses another port. A link cannot start an app that is closed. Review the host under **Connection details**, review the sharing consent and choose **Join a group**. **Sync now** can retry sharing while the host is available.
4. Preview received recordings, then use **Apply changes** on your own PC or restart TF2. Joining never automatically reloads game audio.

Manage members, suggested voices and a changed host address under **Members and advanced settings**.

Only PCs that install and apply the shared collection hear the replacements. People in the same Casual match do not automatically hear them. The microphone is used for saved recordings, not live group voice chat.

## What is shared

Saved recordings, line history and display names are shared with group members. Unsaved microphone previews, local original overrides, TF2 folder paths and RCON passwords stay local. The host can see connection addresses and currently must be trusted with the group history and access credentials.

Invitations are single-use and expire after 24 hours by default. Keep invitations and host links out of public match chat. Never share settings.json, group.json, their backups or Steam launch options; they may contain credentials. Removing someone does not erase audio already copied to that PC, and an isolated old host learns removals only when updated.

No router forwarding or inbound firewall exception is required for this design. Keep the local UI and RCON on loopback. A public tunnel URL still exposes the sync service to requests, so the URL's obscurity is not a security boundary. [Cloudflare's outbound tunnel model](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/).

For this preview, record in the browser while grouped; CLI import is not group-aware yet. Group switching, in-app credential recovery and automatic shared-history cleanup remain pending. If a tunnel dies, close/reopen the app before hosting again.
