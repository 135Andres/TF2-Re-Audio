(() => {
  const $ = selector => document.querySelector(selector);
  translatePage();
  const api = {
    async request(path, options = {}) {
      let response;
      try {
        response = await fetch(path, {
          ...options,
          headers: {
            "Content-Type": options.body instanceof Blob ? options.body.type || "application/octet-stream" : "application/json",
            "X-TF2RA": "1", ...options.headers
          }
        });
      } catch {
        throw new Error(STRINGS.networkFailed);
      }
      const type = response.headers.get("content-type") || "";
      const body = type.includes("json") ? await response.json() : await response.blob();
      if (!response.ok) {
        const error = new Error(body.error || STRINGS.requestFailed);
        error.status = response.status;
        throw error;
      }
      return body;
    },
    get(path) { return this.request(path); },
    post(path, payload, headers = {}) {
      return this.request(path, { method: "POST", body: payload instanceof Blob ? payload : JSON.stringify(payload), headers });
    }
  };
  const state = {
    cls: null, category: "voice_menu", lines: [], allLines: [], recorder: null,
    recording: null, previewUrl: null, configured: false, loadVersion: 0
  };
  const setup = new Setup(api, { notice, refreshState, showDashboard });
  const groupPanel = new GroupPanel(api, { notice, refreshState, showDashboard });

  function notice(message, kind = "info") {
    const el = $("#notice");
    el.textContent = message;
    el.className = `notice ${kind}`;
    el.hidden = false;
  }
  function on(selector, action) {
    $(selector).onclick = async event => {
      const button = event.currentTarget;
      if (button.disabled) return;
      button.disabled = true;
      try { await action(); }
      catch (error) { notice(error.message, "error"); }
      finally { button.disabled = false; }
    };
  }
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function hasTake(line) { return Boolean(line.active && line.active !== "ORIGINAL"); }
  function needsRecording(line) { return !hasTake(line); }
  function lineStatus(line) {
    const labels = [];
    if (line.state.includes("conflict") || line.variants?.some(variant => variant.state.includes("conflict"))) labels.push(STRINGS.conflict);
    if (line.state.includes("local_override")) labels.push(STRINGS.localOverride);
    labels.push(line.effective ? STRINGS.saved : line.has_recording ? STRINGS.variantsRecorded : STRINGS.original);
    if (line.state.includes("pending_share")) labels.push(STRINGS.groupSavedHere);
    if (line.state.includes("pending_apply") || line.variants?.some(variant => variant.state.includes("pending_apply"))) labels.push(STRINGS.pendingApply);
    else if (line.state.includes("applied_requested")) labels.push(STRINGS.applied);
    return labels.join(" · ");
  }
  function showView(view, title) {
    for (const id of ["setup", "dashboard", "class", "settings"]) $("#" + id + "-view").hidden = id !== view;
    if (title) $(title).focus();
  }
  async function refreshState() {
    const data = await api.get("/api/state");
    const labels = {
      connected: STRINGS.tfConnected, not_running: STRINGS.tfClosed, not_configured: STRINGS.tfSetup,
      auth_failed: STRINGS.tfAuth, error: STRINGS.tfError
    };
    $("#tf-status").textContent = labels[data.tf2] || STRINGS.tfChecking;
    $("#tf-status").className = `status-pill ${data.tf2}`;
    groupPanel.refresh(data.collaboration);
    $("#apply-button").hidden = !data.pending_apply;
    $("#apply-button").disabled = Boolean(data.disabled);
    $("#apply-button").textContent = STRINGS.applyCount(data.pending_apply);
    $("#app-version").textContent = `v${data.app_version}`;
    $("#restart-notice").hidden = !data.restart_required;
    $("#disabled-notice").hidden = !data.disabled;
    $("#test-mod-notice").hidden = !data.test_mod_present;
    $("#disable-voices").hidden = Boolean(data.disabled);
    $("#enable-voices").hidden = !data.disabled;
    state.configured = Boolean(data.tf_path);
    if (data.collection_warning) notice(data.collection_warning, "warning");
    return data;
  }
  async function showDashboard() {
    if (!state.configured) {
      showView("setup", "#setup-title");
      notice(STRINGS.chooseBeforeRecording, "warning");
      return;
    }
    showView("dashboard", "#dashboard-title");
    const data = await api.get("/api/classes");
    const grid = $("#class-grid");
    grid.replaceChildren();
    for (const item of data.classes) {
      const button = document.createElement("button");
      button.className = "class-card";
      button.type = "button";
      button.dataset.classId = item.id;
      button.innerHTML = `<span class="class-portrait" aria-hidden="true"><img src="/img/${encodeURIComponent(item.id)}.png" alt="" width="250" height="280"><span hidden>${escapeHtml(item.name.slice(0, 1))}</span></span>
        <span class="class-name">${escapeHtml(item.name)}</span><span class="class-badge" hidden></span>`;
      button.onclick = () => openClass(item.id).catch(error => notice(error.message, "error"));
      button.querySelector("img").onerror = event => {
        event.target.hidden = true;
        button.querySelector(".class-portrait span").hidden = false;
      };
      grid.append(button);
    }
    groupPanel.refresh(groupPanel.data);
    await checkDashboard();
  }

  let checkingDashboard = null;
  async function checkDashboard() {
    const firstCard = $("#class-grid").firstElementChild;
    if (!firstCard || checkingDashboard === firstCard || $("#dashboard-view").hidden || document.hidden) return;
    checkingDashboard = firstCard;
    // Shared takes are read once per pass. Recheck bytes on each pass to detect disk changes.
    const takes = new Map();
    const checkTake = id => {
      if (!takes.has(id)) takes.set(id, (async () => {
        try {
          const metadata = await api.get(`/api/take/${encodeURIComponent(id)}/metadata`);
          const audio = await api.get(`/api/take/${encodeURIComponent(id)}/audio`);
          const digest = await crypto.subtle.digest("SHA-256", await audio.arrayBuffer());
          const sha = [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
          return sha === metadata.sha256 ? "healthy" : "damaged";
        } catch (error) {
          return error.status === 404 ? "damaged" : "unchecked";
        }
      })());
      return takes.get(id);
    };
    try {
      await Promise.all([...$("#class-grid").children].map(async card => {
        let status = "partial";
        try {
          const { lines } = await api.get(`/api/lines?class=${encodeURIComponent(card.dataset.classId)}`);
          const variants = lines.flatMap(line => line.variants);
          const ids = [...new Set(variants.map(variant => variant.effective).filter(Boolean))];
          const results = [];
          for (const id of ids) results.push(await checkTake(id));
          if (results.includes("damaged")) status = "damaged";
          else if (results.includes("unchecked")) status = "unchecked";
          else if (lines.length && variants.length && variants.every(variant => variant.effective)) status = "complete";
        } catch { status = "unchecked"; }
        const badge = card.querySelector(".class-badge");
        card.dataset.audioStatus = status;
        badge.hidden = status === "partial";
        badge.className = `class-badge ${status}`;
        badge.replaceChildren();
        if (!badge.hidden) {
          const icon = document.createElement("span");
          icon.setAttribute("aria-hidden", "true");
          icon.className = "badge-icon";
          icon.textContent = status === "complete" ? "✓" : "!";
          const label = document.createElement("span");
          label.textContent = status === "complete" ? STRINGS.classComplete : status === "damaged" ? STRINGS.classDamaged : STRINGS.classUnchecked;
          badge.append(icon, label);
        }
      }));
    } finally { if (checkingDashboard === firstCard) checkingDashboard = null; }
  }
  window.addEventListener("focus", checkDashboard);
  document.addEventListener("visibilitychange", checkDashboard);
  setInterval(checkDashboard, 30000);
  setInterval(() => { if (!document.hidden) refreshState().catch(() => {}); }, 15000);

  async function openClass(cls) {
    state.cls = cls;
    state.category = "voice_menu";
    $("#line-search").value = "";
    $("#pending-filter").checked = false;
    $("#class-title").textContent = cls[0].toUpperCase() + cls.slice(1);
    showView("class", "#class-title");
    selectTab(state.category);
    await loadLines();
  }
  async function loadLines() {
    const version = ++state.loadVersion;
    const data = await api.get(`/api/lines?class=${encodeURIComponent(state.cls)}`);
    if (version !== state.loadVersion) return;
    state.allLines = data.lines;
    state.lines = data.lines.filter(line => state.category === "all" || line.category === state.category);
    renderLines();
    const medic = data.lines.find(line => line.id === `${state.cls}/medic`);
    $("#start-medic").textContent = medic && needsRecording(medic) ? STRINGS.startMedic : STRINGS.continueRecording;
  }
  function visibleLines() {
    const search = $("#line-search").value.trim().toLowerCase();
    const pending = $("#pending-filter").checked;
    return state.lines.filter(line =>
      (!search || `${line.id} ${line.label}`.toLowerCase().includes(search)) &&
      (!pending || needsRecording(line) || line.state.includes("pending_apply") || line.variants.some(v => v.state.includes("pending_apply"))));
  }
  function button(label, action, className = "secondary") {
    const el = document.createElement("button");
    el.type = "button";
    el.className = `button ${className}`;
    el.textContent = label;
    el.onclick = async () => {
      el.disabled = true;
      try { await action(); }
      catch (error) { notice(error.message, "error"); }
      finally { el.disabled = false; }
    };
    return el;
  }
  function actionsFor(line, holder) {
    const actions = document.createElement("div");
    actions.className = "line-actions";
    actions.append(
      button(STRINGS.playOriginal, () => play(`/api/original/${encodeURIComponent(line.id)}`, holder)),
      button(line.effective ? STRINGS.recordAgain : STRINGS.recordVoice, () => openRecorder(line), "primary")
    );
    if (line.effective) actions.append(button(STRINGS.playTake, () => play(`/api/take/${encodeURIComponent(line.effective)}/audio`, holder)));
    return actions;
  }
  function recoveryFor(line) {
    const actions = document.createElement("div");
    actions.className = "line-actions recovery-actions";
    actions.append(
      button(STRINGS.history, () => openHistory(line)),
      button(line.state.includes("local_override") ? STRINGS.useCollection : STRINGS.useOriginal,
        () => changeLine("/api/override", line, { use_original: !line.state.includes("local_override") })),
      button(STRINGS.restore, () => changeLine("/api/restore", line)),
      button(STRINGS.undo, () => changeLine("/api/undo", line))
    );
    return actions;
  }
  function renderLines() {
    const list = $("#line-list");
    const expanded = new Set([...list.querySelectorAll("article > details[open]")].map(details => details.parentElement.dataset.lineId));
    const variantsExpanded = new Set([...list.querySelectorAll('.line-toggle[aria-expanded="true"]')].map(toggle => toggle.closest("article").dataset.lineId));
    list.replaceChildren();
    const visible = visibleLines();
    $("#class-progress").textContent = STRINGS.linesShown(visible.length, state.lines.filter(line => line.has_recording).length);
    if (!visible.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = STRINGS.noMatches;
      list.append(empty);
    }
    for (const line of visible) {
      const article = document.createElement("article");
      article.className = "line-card";
      article.dataset.lineId = line.id;
      const mainVoice = line.variants.length > 1 ? { ...line.variants[0], label: line.label } : line;
      article.innerHTML = `<div class="line-summary"><h2 tabindex="-1">${escapeHtml(line.label)}</h2>
        <p class="technical">${STRINGS.replaces(mainVoice.files.length)}</p><p class="line-state">${escapeHtml(lineStatus({ ...line, effective: mainVoice.effective }))}</p></div>`;
      article.append(actionsFor(mainVoice, article));
      if (line.variants.length > 1) {
        const panel = document.createElement("div");
        panel.className = "variant-list";
        panel.id = `variants-${line.id}`;
        panel.hidden = !variantsExpanded.has(line.id);
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "line-toggle";
        toggle.setAttribute("aria-label", `${line.label} · ${STRINGS.variants}`);
        toggle.setAttribute("aria-expanded", String(!panel.hidden));
        toggle.setAttribute("aria-controls", panel.id);
        toggle.innerHTML = `<span class="line-chevron" aria-hidden="true"></span>${escapeHtml(line.label)}<span class="variant-hint" aria-hidden="true">${STRINGS.variants}</span>`;
        article.querySelector("h2").replaceChildren(toggle);
        const populateVariants = () => {
          if (panel.childElementCount) return;
          const help = document.createElement("p");
          help.className = "help";
          help.textContent = STRINGS.variantHelp;
          const variants = document.createElement("ul");
          variants.className = "variant-items";
          line.variants.slice(1).forEach(variant => {
            const row = document.createElement("li");
            row.className = "variant-row";
            row.dataset.lineId = variant.id;
            row.innerHTML = `<div class="variant-summary"><h3><svg class="variant-mark" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3v6m0 6v6M3 12h6m6 0h6"/></svg>${escapeHtml(line.label)}</h3>
              <p class="line-state">${escapeHtml(variant.inherited ? STRINGS.inherited : lineStatus(variant))}</p></div>`;
            const version = { ...variant, label: `${line.label} · ${STRINGS.variant}` };
            row.append(actionsFor(version, row));
            const more = document.createElement("details");
            more.className = "variant-details";
            more.innerHTML = `<summary>${STRINGS.details}</summary>`;
            more.append(recoveryFor(version));
            row.append(more);
            variants.append(row);
          });
          panel.append(help, variants);
        };
        toggle.onclick = () => {
          panel.hidden = !panel.hidden;
          toggle.setAttribute("aria-expanded", String(!panel.hidden));
          if (!panel.hidden) populateVariants();
        };
        if (!panel.hidden) populateVariants();
        article.append(panel);
      }
      // Whole-line recovery stays separate from the individual variants.
      const details = document.createElement("details");
      details.className = "line-details";
      details.innerHTML = `<summary>${STRINGS.details}</summary>`;
      if (mainVoice !== line) {
        const mainRecovery = document.createElement("div");
        mainRecovery.innerHTML = `<h3>${STRINGS.mainVoice}</h3>`;
        mainRecovery.append(recoveryFor(mainVoice));
        details.append(mainRecovery);
        details.insertAdjacentHTML("beforeend", `<h3>${STRINGS.allVersions}</h3>`);
      }
      details.append(recoveryFor(line));
      details.insertAdjacentHTML("beforeend", `<p class="technical">${escapeHtml(line.id)}</p><p class="help">${STRINGS.restoreHelp}</p>`);
      details.open = expanded.has(line.id);
      article.append(details);
      list.append(article);
    }
  }
  async function changeLine(endpoint, line, changes = {}) {
    const result = await api.post(endpoint, { line_id: line.id, ...changes });
    const noUndo = endpoint === "/api/undo" && !result.event_id;
    notice(result.install_error || (noUndo ? STRINGS.nothingToUndo : STRINGS.lineChanged), result.install_error || noUndo ? "warning" : "success");
    await refreshState();
    await loadLines();
    if (!$("#history-dialog").open) focusLine(line.id);
  }
  function focusLine(lineId) {
    const base = lineId.split("#")[0];
    $(`article[data-line-id="${CSS.escape(base)}"] h2`)?.focus();
  }
  function focusRecording(lineId) {
    const base = lineId.split("#")[0];
    const article = $(`article[data-line-id="${CSS.escape(base)}"]`);
    const variant = article?.querySelector(`.variant-row[data-line-id="${CSS.escape(lineId)}"] .primary`);
    const target = variant && !variant.closest(".variant-list").hidden ? variant : article?.querySelector(":scope > .line-actions .primary");
    (target || $("#class-title")).focus();
  }
  async function openHistory(line) {
    const data = await api.get(`/api/history?line_id=${encodeURIComponent(line.id)}`);
    const list = $("#history-list");
    list.replaceChildren();
    $("#history-title").textContent = STRINGS.historyTitle(line.label);
    state.historyLine = line.id;
    if (!data.takes.length) {
      const empty = document.createElement("p");
      empty.textContent = STRINGS.historyEmpty;
      list.append(empty);
    }
    for (const take of data.takes.slice().reverse()) {
      const row = document.createElement("article");
      row.className = "history-take";
      const label = document.createElement("p");
      label.textContent = `${STRINGS.takeLabel({ ...take, author_member_id: groupPanel.authorName(take) })}${take.active ? ` · ${STRINGS.activeTake}` : ""}`;
      const audio = document.createElement("audio");
      audio.preload = "none";
      audio.src = `/api/take/${encodeURIComponent(take.take_id)}/audio`;
      row.append(label, player(audio), button(data.state.includes("conflict") ? STRINGS.resolve : STRINGS.restoreTake, async () => {
        await changeLine(data.state.includes("conflict") ? "/api/resolve" : "/api/set-active", line, { take_id: take.take_id });
        $("#history-dialog").close();
      }));
      list.append(row);
    }
    $("#history-dialog").showModal();
  }
  function play(url, holder) {
    document.querySelectorAll("audio").forEach(audio => audio.pause());
    let audio = holder.querySelector(":scope > .player > .line-preview");
    if (!audio) {
      audio = document.createElement("audio");
      audio.className = "line-preview";
      holder.append(player(audio));
    }
    audio.src = url;
    return audio.play().catch(() => notice(STRINGS.playHelp));
  }
  // Replaces the browser's native audio controls with a play button, seek bar and time.
  function player(audio) {
    const wrap = document.createElement("div");
    wrap.className = "player";
    if (audio.parentNode) audio.replaceWith(wrap);
    audio.controls = false;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "player-toggle";
    const seek = document.createElement("input");
    seek.type = "range";
    seek.max = 1000;
    seek.setAttribute("aria-label", STRINGS.playerSeek);
    const time = document.createElement("span");
    time.className = "player-time";
    // Voice lines last about a second, so tenths matter.
    const clock = seconds => Number.isFinite(seconds) ? `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(1).padStart(4, "0")}` : "0:00.0";
    const update = () => {
      toggle.textContent = audio.paused ? "▶" : "❚❚";
      toggle.setAttribute("aria-label", audio.paused ? STRINGS.playerPlay : STRINGS.playerPause);
      seek.value = audio.duration ? audio.currentTime / audio.duration * 1000 : 0;
      seek.style.setProperty("--fill", `${seek.value / 10}%`);
      time.textContent = `${clock(audio.currentTime)} / ${clock(audio.duration)}`;
    };
    for (const event of ["play", "pause", "timeupdate", "durationchange", "ended", "emptied"]) audio.addEventListener(event, update);
    audio.addEventListener("ended", () => { audio.currentTime = 0; });
    toggle.onclick = () => audio.paused ? audio.play().catch(() => notice(STRINGS.playHelp)) : audio.pause();
    seek.oninput = () => { if (audio.duration) audio.currentTime = seek.value / 1000 * audio.duration; };
    wrap.append(audio, toggle, seek, time);
    update();
    return wrap;
  }
  player($("#take-preview"));
  function cleanupRecorder() {
    cancelAnimationFrame(state.timer);
    state.recorder?.destroy();
    state.recorder = null;
    $("#take-preview").pause();
    $("#take-preview").removeAttribute("src");
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = null;
  }
  function openRecorder(line) {
    cleanupRecorder();
    state.recording = line;
    $("#recorder-line").textContent = `${line.label} · ${STRINGS.replaces(line.files.length)}`;
    $("#recorder-files").replaceChildren(...line.files.map(path => {
      const li = document.createElement("li");
      li.textContent = path;
      return li;
    }));
    resetRecorder();
    state.recorder = new Recorder(level => {
      const value = Math.round(level * 100);
      $("#level-bar").style.width = `${value}%`;
      $("#level-meter").setAttribute("aria-valuenow", value);
      $("#level-text").textContent = state.recorder?.stream ? (level > 0.03 ? STRINGS.micActive : STRINGS.quiet) : STRINGS.notRecording;
    }, message => {
      $("#recorder-error").hidden = false;
      $("#recorder-error").textContent = message;
    });
    if (!$("#recorder-dialog").open) $("#recorder-dialog").showModal();
    state.recorder.devices($("#microphone"));
  }
  function resetRecorder() {
    for (const id of ["recorder-error", "take-warning", "take-preview", "retake-button", "discard-button", "save-button"]) $("#" + id).hidden = true;
    $("#record-button").disabled = false;
    $("#stop-button").disabled = true;
    $("#microphone").disabled = false;
    $("#test-mic").disabled = false;
    $("#timer").textContent = "00:00.0";
    $("#level-text").textContent = STRINGS.notRecording;
    $("#level-bar").style.width = "0%";
    $("#level-meter").setAttribute("aria-valuenow", "0");
  }
  function updateTimer(recorder) {
    if (state.recorder !== recorder || recorder.media?.state !== "recording") return;
    const elapsed = Math.min(10, (performance.now() - recorder.started) / 1000);
    $("#timer").textContent = `00:${elapsed.toFixed(1).padStart(4, "0")}`;
    state.timer = requestAnimationFrame(() => updateTimer(recorder));
  }
  async function startRecording() {
    const recorder = state.recorder;
    $("#recorder-error").hidden = true;
    $("#record-button").disabled = true;
    $("#test-mic").disabled = true;
    $("#microphone").disabled = true;
    const ok = await recorder.start($("#microphone").value, stopRecording);
    if (state.recorder !== recorder) return;
    if (!ok) {
      $("#record-button").disabled = false;
      $("#test-mic").disabled = false;
      $("#microphone").disabled = false;
      return;
    }
    $("#stop-button").disabled = false;
    updateTimer(recorder);
  }
  async function stopRecording() {
    const recorder = state.recorder;
    if (!recorder?.media || recorder.stopping) return;
    cancelAnimationFrame(state.timer);
    $("#stop-button").disabled = true;
    const elapsed = Math.min(10, (performance.now() - recorder.started) / 1000);
    const blob = await recorder.stop($("#trim-silence").checked);
    if (state.recorder !== recorder || !$("#recorder-dialog").open) return;
    if (!blob) { $("#record-button").disabled = false; return; }
    $("#timer").textContent = `00:${elapsed.toFixed(1).padStart(4, "0")}`;
    showPreview(blob);
    await warnRecording(blob, recorder);
  }
  function showPreview(blob) {
    if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
    state.previewUrl = URL.createObjectURL(blob);
    $("#take-preview").src = state.previewUrl;
    for (const id of ["take-preview", "retake-button", "discard-button", "save-button"]) $("#" + id).hidden = false;
    $("#save-button").disabled = false;
  }
  async function warnRecording(blob, recorder) {
    const data = new DataView(await blob.arrayBuffer());
    let sum = 0, clipped = 0;
    const count = (data.byteLength - 44) / 2;
    for (let i = 44; i + 1 < data.byteLength; i += 2) {
      const sample = data.getInt16(i, true);
      sum += (sample / 32768) ** 2;
      if (Math.abs(sample) >= 32767) clipped++;
    }
    if (state.recorder !== recorder) return;
    const warnings = [];
    if (Math.sqrt(sum / Math.max(1, count)) < 10 ** (-45 / 20)) warnings.push(STRINGS.silent);
    if (clipped > count * 0.001) warnings.push(STRINGS.clipping);
    $("#take-warning").hidden = !warnings.length;
    $("#take-warning").textContent = warnings.join(" ");
  }
  async function saveRecording() {
    const recorder = state.recorder, line = state.recording;
    $("#save-button").disabled = true;
    try {
      const result = await api.post("/api/take", recorder.audio, { "X-Line-ID": line.id });
      if (state.recorder === recorder) $("#recorder-dialog").close();
      notice(result.install_error || STRINGS.savedMessage, result.install_error ? "warning" : "success");
      await refreshState();
      await loadLines();
      if (!$("#recorder-dialog").open) focusRecording(line.id);
    } catch (error) {
      if (state.recorder !== recorder) { notice(error.message, "error"); return; }
      $("#recorder-error").hidden = false;
      $("#recorder-error").textContent = error.message;
      $("#save-button").disabled = false;
      $("#save-button").focus();
    }
  }
  async function nextLine(preferMedic = false) {
    const medic = state.allLines.find(line => line.id === `${state.cls}/medic`);
    const line = (preferMedic && medic && needsRecording(medic) ? medic : null) ||
      (preferMedic ? state.allLines : visibleLines()).find(needsRecording);
    if (line) openRecorder(line);
    else notice(STRINGS.categoryComplete, "success");
  }
  function selectTab(category) {
    document.querySelectorAll(".tab").forEach(tab => {
      const selected = tab.dataset.category === category;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-selected", selected);
      tab.tabIndex = selected ? 0 : -1;
    });
    $("#line-list").setAttribute("aria-labelledby", `tab-${category}`);
  }

  on("#start-solo", showDashboard);
  on("#back-dashboard", showDashboard);
  on("#back-settings", showDashboard);
  on("#settings-button", async () => { await setup.open(); showView("settings", "#settings-title"); });
  on("#start-medic", () => nextLine(true));
  on("#next-line", () => nextLine());
  on("#apply-button", async () => {
    const result = await api.post("/api/apply", {});
    notice(result.install_error || (result.result === "sent" ? STRINGS.applySent : STRINGS.connectionFailed), result.result === "sent" ? "success" : "warning");
    await refreshState();
    if (state.cls) await loadLines();
  });
  // Recording buttons retain their disabled state while recording/decoding.
  $("#record-button").onclick = startRecording;
  $("#stop-button").onclick = stopRecording;
  $("#test-mic").onclick = async () => {
    const recorder = state.recorder;
    $("#test-mic").disabled = true;
    $("#record-button").disabled = true;
    await recorder.test($("#microphone").value);
    if (state.recorder === recorder) {
      $("#test-mic").disabled = false;
      $("#record-button").disabled = false;
    }
  };
  $("#recorder-dialog").onclose = () => {
    cleanupRecorder();
    if (state.recording) focusRecording(state.recording.id);
  };
  $("#recorder-dialog").oncancel = cleanupRecorder;
  $("#retake-button").onclick = () => openRecorder(state.recording);
  $("#discard-button").onclick = () => $("#recorder-dialog").close();
  $("#save-button").onclick = saveRecording;
  $("#trim-silence").onchange = async () => {
    if (!state.recorder?.audio || state.recorder.media) return;
    showPreview(state.recorder.prepare($("#trim-silence").checked));
    await warnRecording(state.recorder.audio, state.recorder);
  };
  $("#history-dialog").onclose = () => {
    $("#history-list").querySelectorAll("audio").forEach(audio => audio.pause());
    if (state.historyLine) focusLine(state.historyLine);
  };
  $("#line-search").oninput = renderLines;
  $("#pending-filter").onchange = renderLines;
  const tabs = [...document.querySelectorAll(".tab")];
  tabs.forEach((tab, index) => {
    tab.onclick = async () => {
      state.category = tab.dataset.category;
      selectTab(state.category);
      state.lines = state.allLines.filter(line => state.category === "all" || line.category === state.category);
      renderLines();
    };
    tab.onkeydown = event => {
      const targets = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index + tabs.length - 1) % tabs.length, Home: 0, End: tabs.length - 1 };
      if (!(event.key in targets)) return;
      event.preventDefault();
      const next = tabs[targets[event.key]];
      next.focus();
      next.click();
    };
  });
  window.addEventListener("tf-configured", () => { state.configured = true; });
  (async () => {
    const data = await refreshState();
    if (state.configured) await showDashboard();
    else {
      showView("setup", "#setup-title");
      if (data.setup_error) { $("#setup-error").hidden = false; $("#setup-error").textContent = data.setup_error; }
      await setup.load();
    }
    await groupPanel.openInvitation();
  })().catch(error => notice(error.message, "error"));
})();
