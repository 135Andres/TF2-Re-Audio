window.Setup = class {
  constructor(api, ui) {
    this.api = api;
    this.ui = ui;
    this.bind("#save-tf", () => this.save(this.el("#tf-path").value, "#setup-error"));
    this.bind("#choose-folder", () => this.el("#tf-path").focus());
    this.bind("#settings-save", () => this.save(this.el("#settings-tf-path").value));
    this.bind("#save-rcon-port", () => this.savePort());
    this.bind("#copy-options", () => this.copyOptions());
    this.bind("#check-connection", () => this.checkConnection());
    this.bind("#apply-later", () => this.ui.notice(STRINGS.applyLaterHelp));
    this.bind("#remove-test-mod", () => this.removeTestMod());
    this.bind("#restart-confirmed", async () => {
      await this.api.post("/api/restart-confirmed", {});
      this.ui.notice(STRINGS.restartDismissed);
      await this.ui.refreshState();
    });
    this.bind("#export-collection", () => this.exportCollection());
    this.bind("#import-collection", () => this.importCollection());
    this.bind("#disable-voices", () => this.setEnabled(false));
    this.bind("#enable-voices", () => this.setEnabled(true));
    this.bind("#delete-collection", () => this.deleteCollection());
    this.bind("#uninstall", () => this.uninstall());
  }

  el(selector) { return document.querySelector(selector); }

  bind(selector, action) {
    this.el(selector).onclick = async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try { await action(); }
      catch (error) { this.ui.notice(error.message, "error"); }
      finally { button.disabled = false; }
    };
  }

  async load() {
    const data = await this.api.get("/api/installs");
    const list = this.el("#installs");
    list.replaceChildren();
    for (const item of data.installs) {
      const button = document.createElement("button");
      button.className = "install-option";
      button.type = "button";
      button.textContent = `${item.ok ? STRINGS.useInstall : STRINGS.checkInstall}: ${item.tf_path} — ${item.detail}`;
      button.disabled = !item.ok;
      button.onclick = () => {
        this.el("#tf-path").value = item.tf_path;
        this.save(item.tf_path, "#setup-error");
      };
      list.append(button);
    }
  }

  async open() {
    const data = await this.api.get("/api/settings");
    this.el("#settings-tf-path").value = data.tf_path || "";
    this.el("#rcon-port").value = data.rcon_port || 27015;
    await this.ui.refreshState();
  }

  async save(value, messageSelector = "#settings-message") {
    if (!value.trim()) return this.ui.notice(STRINGS.folderRequired, "warning");
    const message = this.el(messageSelector);
    message.hidden = true;
    try {
      await this.api.post("/api/settings", { tf_path: value.trim() });
      this.ui.notice(STRINGS.folderSaved, "success");
      window.dispatchEvent(new Event("tf-configured"));
      await this.ui.refreshState();
      await this.ui.showDashboard();
    } catch (error) {
      message.hidden = false;
      message.textContent = error.message;
      message.className = "callout error";
    }
  }

  async savePort() {
    const port = Number(this.el("#rcon-port").value);
    if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error(STRINGS.portInvalid);
    await this.api.post("/api/settings", { rcon_port: port });
    this.el("#launch-options").hidden = true;
    this.ui.notice(STRINGS.portSaved, "success");
    await this.ui.refreshState();
  }

  async copyOptions() {
    const data = await this.api.post("/api/launch-options", {});
    const options = this.el("#launch-options");
    options.value = data.launch_options;
    options.hidden = false;
    try {
      await navigator.clipboard.writeText(data.launch_options);
      this.ui.notice(STRINGS.optionsCopied, "success");
    } catch {
      options.focus();
      options.select();
      this.ui.notice(STRINGS.optionsFallback);
    }
  }

  async checkConnection() {
    const data = await this.api.post("/api/check-connection", {});
    this.ui.notice(data.result === "connected" ? STRINGS.tfConnected : STRINGS.connectionFailed,
      data.result === "connected" ? "success" : "warning");
    await this.ui.refreshState();
  }

  async removeTestMod() {
    if (!confirm(STRINGS.confirmTest)) return;
    await this.api.post("/api/remove-test-mod", {});
    this.ui.notice(STRINGS.testRemoved, "success");
    await this.ui.refreshState();
  }

  async exportCollection() {
    const blob = await this.api.get("/api/export");
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "TF2ReAudio-collection.zip";
    document.body.append(link);
    link.click();
    link.remove();
    // Give the browser time to start the download before releasing the blob.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    this.ui.notice(STRINGS.exported, "success");
  }

  async importCollection() {
    const file = this.el("#import-file").files[0];
    if (!file) throw new Error(STRINGS.zipRequired);
    if (file.size > 64 * 1024 * 1024) throw new Error(STRINGS.zipTooLarge);
    const blob = new Blob([file], { type: "application/zip" });
    const result = await this.api.post("/api/import", blob);
    this.ui.notice(result.install_error || STRINGS.imported, result.install_error ? "warning" : "success");
    this.el("#import-file").value = "";
    await this.ui.refreshState();
  }

  async setEnabled(enabled) {
    if (!enabled && !confirm(STRINGS.confirmDisable)) return;
    await this.api.post(enabled ? "/api/enable" : "/api/disable", {});
    this.ui.notice(enabled ? STRINGS.voicesEnabled : STRINGS.voicesDisabled, "success");
    await this.ui.refreshState();
  }

  async deleteCollection() {
    if (!confirm(STRINGS.confirmDelete)) return;
    await this.api.post("/api/uninstall", { delete_collection: true });
    this.ui.notice(STRINGS.collectionDeleted, "success");
    await this.ui.refreshState();
  }

  async uninstall() {
    const deleteCollection = this.el("#uninstall-delete").checked;
    if (!confirm(deleteCollection ? STRINGS.confirmUninstallDelete : STRINGS.confirmUninstall)) return;
    await this.api.post("/api/uninstall", { delete_collection: deleteCollection }).then(data => {
      this.el("#remove-options").value = data.launch_options;
      this.el("#uninstall-guide").hidden = false;
    });
    this.ui.notice(STRINGS.uninstallDone);
    await this.ui.refreshState();
  }
};
