/* Group controls use the local API; no token or remote host is exposed to fetch. */
class GroupPanel {
  constructor(api, hooks) {
    this.api = api;
    this.hooks = hooks;
    this.data = { status: "solo" };
    this.dialog = document.querySelector("#group-dialog");
    this.bind("#group-button", () => this.open());
    this.bind("#show-join", () => this.open());
    this.bind("#group-close", () => this.dialog.close());
    this.dialog.onclose = () => document.querySelector("#group-button").focus();
    this.bind("#group-create", () => this.createOrJoin("create"));
    this.bind("#group-join", () => this.createOrJoin("join"));
    this.bind("#group-invite", async () => {
      const result = await this.api.post("/api/group/invite", {});
      this.el("#group-invitation").value = [result.url, result.code].filter(Boolean).join("\n");
      this.el("#group-invitation-area").hidden = false;
      if (!result.url) this.message(STRINGS.inviteNeedsHost);
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
    this.message(STRINGS.groupJoined);
  }
  async reload() {
    this.render(await this.api.get("/api/group"));
    await this.hooks.refreshState();
  }
  async open() {
    await this.reload();
    if (!this.dialog.open) this.dialog.showModal();
    this.el("#group-title").focus();
  }
  authorName(take) {
    return this.data.members?.find(member => member.member_id === take.author_member_id || member.device_id === take.device_id)?.display_name || take.author_member_id;
  }
  refresh(data) {
    this.data = data || { status: "solo" };
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
