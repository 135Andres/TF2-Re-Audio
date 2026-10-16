/* Group controls use the local API; no token or remote host is exposed to fetch. */
class GroupPanel {
  constructor(api, hooks) {
    this.api = api;
    this.hooks = hooks;
    this.data = { status: "solo" };
    this.dialog = document.querySelector("#group-dialog");
    window.addEventListener("hashchange", () => this.openInvitation().catch(error => this.message(error.message)));
    this.bind("#group-button", () => this.open());
    this.bind("#show-join", () => this.open("join"));
    this.bind("#group-choose-invite", () => this.choose("create"));
    this.bind("#group-choose-join", () => this.choose("join"));
    this.bind("#group-use-invitation", () => this.useInvitation(this.el("#group-paste").value));
    this.bind("#group-close", () => this.dialog.close());
    this.dialog.onclose = () => document.querySelector("#group-button").focus();
    this.bind("#group-create", () => this.createOrJoin("create"));
    this.bind("#group-join", () => this.createOrJoin("join"));
    this.bind("#group-invite", async () => {
      if (!this.readyToInvite()) throw new Error(STRINGS.sharingNotReady);
      const result = await this.api.post("/api/group/invite", {});
      if (!result.url) throw new Error(STRINGS.sharingNotReady);
      const link = "http://127.0.0.1:8440/#join?host=" + encodeURIComponent(this.hostUrl(result.url));
      this.invitationHost = result.url;
      this.el("#group-invitation").value = [link, result.code, "", STRINGS.inviteInstructions].join("\n");
      this.el("#group-invitation-area").hidden = false;
    });
    this.bind("#group-copy", async () => {
      const text = this.el("#group-invitation");
      try {
        await navigator.clipboard.writeText(text.value);
        this.message(STRINGS.inviteCopied);
      } catch {
        text.focus(); text.select();
        this.message(STRINGS.copyManually);
      }
    });
    this.bind("#group-sync", async () => {
      const result = await this.api.post("/api/group/sync", {});
      if (result.error) throw new Error(result.error);
      await this.reload();
    });
    this.bind("#group-update", () => this.action("link", { url: this.el("#group-update-link").value.trim() }));
    this.bind("#group-host", () => this.action("host", { enabled: !this.data.hosting }));
  }
  el(selector) { return document.querySelector(selector); }
  message(text) { this.el("#group-message").textContent = text; }
  bind(selector, action) {
    this.el(selector).onclick = event => this.perform(event.currentTarget, action);
  }
  async perform(button, action) {
    if (button.disabled) return;
    button.disabled = true;
    this.message("");
    try { await action(); }
    catch (error) { this.message(error.message); }
    finally { button.disabled = false; }
  }
  async action(name, payload) {
    await this.api.post(`/api/group/${name}`, payload);
    await this.reload();
    this.message(STRINGS.groupChanged);
  }
  async createOrJoin(action) {
    await this.api.post(`/api/group/${action}`, {
      name: this.el("#group-name").value.trim(),
      display_name: this.el("#group-display-name").value.trim(),
      url: this.el("#group-join-link").value.trim(),
      code: this.el("#group-code").value.trim(),
      share_existing: this.el("#group-consent").checked
    });
    this.el("#group-code").value = "";
    await this.reload();
    this.el("#group-title").focus();
    this.message(action === "create" ? STRINGS.groupCreated : STRINGS.groupJoined);
  }
  async reload() {
    this.render(await this.api.get("/api/group"));
    await this.hooks.refreshState();
  }
  choose(mode) {
    this.message("");
    this.el("#group-form").hidden = false;
    this.el("#group-flow-title").textContent = mode === "create" ? STRINGS.inviteFriends : STRINGS.join;
    this.el("#group-create-fields").hidden = mode !== "create";
    this.el("#group-create").hidden = mode !== "create";
    this.el("#group-join-fields").hidden = mode !== "join";
    this.el("#group-paste-area").hidden = mode !== "join";
    this.el("#group-join").hidden = mode !== "join";
  }
  hostUrl(value) {
    const url = new URL(value);
    if (url.username || url.password || url.hash || url.search ||
        !(url.protocol === "https:" || (url.protocol === "http:" && ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)))) {
      throw new Error(STRINGS.invalidInvitation);
    }
    return value;
  }
  useInvitation(text) {
    try {
      const candidate = text.trim().split(/\s+/)[0];
      const link = new URL(candidate);
      let host;
      if (link.hash.startsWith("#join?")) {
        if (link.protocol !== "http:" || link.hostname !== "127.0.0.1") throw new Error();
        host = new URLSearchParams(link.hash.slice(6)).get("host");
      } else host = candidate;
      host = this.hostUrl(host);
      const code = text.match(/\bTF2-(?:[A-Z0-9]{4}-){1,2}[A-Z0-9]{4}\b/i)?.[0] || "";
      this.el("#group-join-link").value = host;
      this.el("#group-code").value = code.toUpperCase();
      this.el("#group-address").open = false;
      this.el("#group-paste-area").open = false;
      this.message(STRINGS.inviteReview);
      this.el(code ? "#group-display-name" : "#group-code").focus();
    } catch { throw new Error(STRINGS.invalidInvitation); }
  }
  async openInvitation() {
    if (!location.hash.startsWith("#join?")) return;
    const invitation = location.href;
    history.replaceState(null, "", location.pathname + location.search);
    await this.open("join");
    if (this.data.status !== "solo") { this.message(STRINGS.alreadyGrouped); return; }
    this.useInvitation(invitation);
  }
  readyToInvite() { return Boolean(this.data.url && (this.data.hosting || this.data.status === "synced")); }
  async open(mode) {
    await this.reload();
    if (!this.dialog.open) this.dialog.showModal();
    if (mode && this.data.status === "solo") this.choose(mode);
    this.el("#group-title").focus();
  }
  authorName(take) {
    return this.data.members?.find(member => member.member_id === take.author_member_id || member.device_id === take.device_id)?.display_name || take.author_member_id;
  }
  refresh(data) {
    this.data = data || { status: "solo" };
    this.el("#group-invite").disabled = !this.readyToInvite();
    this.el("#group-invite-help").textContent = this.readyToInvite() ? STRINGS.sharingReady : STRINGS.sharingNotReady;
    if (!this.readyToInvite() || (this.invitationHost && this.invitationHost !== this.data.url)) {
      this.el("#group-invitation-area").hidden = true;
      this.el("#group-invitation").value = "";
    }

    const labels = { solo: STRINGS.solo, hosting: STRINGS.groupHosting, synced: STRINGS.groupSynced,
      auth_failed: STRINGS.groupAuth, update_required: STRINGS.groupUpdate };
    const label = labels[this.data.status] || STRINGS.groupOffline(this.data.pending_share || 0);
    this.el("#group-status").textContent = label;
    this.el("#group-detail-status").textContent = label;
    this.el("#group-status").title = this.data.status === "solo" ? "" : STRINGS.groupPending(this.data.pending_share || 0);
    this.el("#group-sync").disabled = this.data.status === "auth_failed";
    for (const card of document.querySelectorAll(".class-card")) {
      let hint = card.querySelector(".group-suggestion");
      const mid = this.data.suggested_voices?.[card.dataset.classId];
      const member = this.data.members?.find(item => item.member_id === mid);
      if (member && !hint) {
        hint = document.createElement("span"); hint.className = "group-suggestion help"; card.append(hint);
      }
      if (hint) { hint.textContent = member ? STRINGS.suggestedMember(member.display_name) : ""; hint.hidden = !member; }
    }
  }
  render(data) {
    this.refresh(data);
    const solo = data.status === "solo";
    this.el("#group-solo-controls").hidden = !solo;
    this.el("#group-member-controls").hidden = solo;
    this.el("#group-existing").textContent = STRINGS.groupSoloCount(data.existing_recordings || 0);
    this.el("#group-invite").hidden = !data.is_admin;
    if (data.error) this.message(data.error);
    if (solo) return;
    this.el("#group-name-display").textContent = data.name;
    this.el("#group-update-link").value = data.url || "";
    this.el("#group-host").textContent = data.hosting ? STRINGS.stopHosting : STRINGS.hostForGroup;
    const list = this.el("#group-members");
    list.replaceChildren();
    for (const member of data.members) {
      const row = document.createElement("li");
      const label = document.createElement("span");
      label.textContent = `${member.display_name} · ${member.role === "admin" ? STRINGS.groupAdmin : STRINGS.groupMember}`;
      row.append(label);
      if (data.is_admin && member.member_id !== data.member_id) {
        if (member.role !== "admin") row.append(this.button(STRINGS.promoteMember, () => this.action("promote", { member_id: member.member_id })));
        row.append(this.button(STRINGS.removeMember, async () => {
          if (window.confirm(STRINGS.confirmRemoveMember(member.display_name))) {
            await this.action("remove", { member_id: member.member_id });
            this.el("#group-title").focus();
          }
        }));
      }
      list.append(row);
    }
    const cast = this.el("#group-suggestions");
    cast.replaceChildren();
    for (const cls of ["scout", "soldier", "pyro", "demoman", "heavy", "engineer", "medic", "sniper", "spy"]) {
      const label = document.createElement("label");
      label.textContent = cls.charAt(0).toUpperCase() + cls.slice(1);
      const select = document.createElement("select");
      select.disabled = !data.is_admin;
      select.append(new Option(STRINGS.noSuggestion, ""));
      for (const member of data.members) select.append(new Option(member.display_name, member.member_id));
      select.value = data.suggested_voices[cls] || "";
      select.onchange = () => {
        this.perform(select, () => this.action("suggest", { class: cls, member_id: select.value || null }));
      };
      label.append(select); cast.append(label);
    }
  }
  button(text, action) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "button secondary"; button.textContent = text;
    button.onclick = () => this.perform(button, action);
    return button;
  }
}
