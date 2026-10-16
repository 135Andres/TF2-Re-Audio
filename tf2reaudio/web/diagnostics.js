/* Memory-only diagnostics collector. It keeps fixed codes only: never messages, stacks, URLs, device labels or typed text. */
window.Diagnostics = (() => {
  const $ = selector => document.querySelector(selector);
  const ID = /^[a-z][a-z0-9_]{0,39}$/;
  const OUTCOMES = ["start", "ok", "failed", "unsupported", "not_tested", "blocked"];
  const DETAILS = {
    status: "number", count: "number", duration_ms: "number", route: "string", step: "string", reason: "string",
    get_user_media: "boolean", media_recorder: "boolean", audio_context: "boolean", secure_context: "boolean"
  };
  const queue = [];
  let scriptErrors = 0;

  function clean(details) {
    const result = {};
    for (const [key, type] of Object.entries(DETAILS)) {
      const value = details?.[key];
      if (typeof value !== type) continue;
      if (type === "string" && !ID.test(value)) continue;
      if (type === "number" && !Number.isInteger(value)) continue;
      result[key] = value;
    }
    return result;
  }
  async function post(path, body, timeout) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      return await fetch(path, {
        method: "POST", body: JSON.stringify(body), signal: controller.signal,
        headers: { "Content-Type": "application/json", "X-TF2RA": "1" }
      });
    } finally { clearTimeout(timer); }
  }
  function emit(action, outcome, code, details = {}) {
    if (!ID.test(action) || !OUTCOMES.includes(outcome) || !ID.test(code)) return;
    const event = { action, outcome, code, details: clean(details) };
    queue.push({ ...event, ts: new Date().toISOString() });
    if (queue.length > 100) queue.shift();
    // No retry, and failures here are never reported (that would loop).
    post("/api/diagnostics/event", event, 2000).catch(() => {});
  }
  function capabilities() {
    return {
      get_user_media: Boolean(navigator.mediaDevices?.getUserMedia), media_recorder: Boolean(window.MediaRecorder),
      audio_context: Boolean(window.AudioContext || window.webkitAudioContext), secure_context: Boolean(window.isSecureContext)
    };
  }
  function results() {
    const step = $("#diag-step").value, outcome = $("#diag-outcome").value, reason = $("#diag-reason").value;
    return step && outcome !== "not_tested" ? [{ step, outcome, ...(reason ? { reason } : {}) }] : [];
  }
  function message(text) { $("#diagnostics-message").textContent = text; }
  function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportFallback() {
    const report = {
      kind: "browser-only", note: STRINGS.diagnosticsBrowserNote, created: new Date().toISOString(),
      capabilities: capabilities(), events: queue, test_results: results()
    };
    download(new Blob([JSON.stringify(report, null, 1)], { type: "application/json" }),
      `TF2ReAudio-browser-report-${report.created.replace(/[-:]/g, "").slice(0, 15)}Z.json`);
    message(STRINGS.diagnosticsBrowserSaved);
  }
  async function exportReport() {
    let response;
    try { response = await post("/api/diagnostics/export", { test_results: results() }, 15000); }
    catch { message(STRINGS.diagnosticsOffline); return exportFallback(); }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return message(body.error || STRINGS.requestFailed);
    }
    const name = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") || "")?.[1];
    download(await response.blob(), name || "TF2ReAudio-diagnostics.zip");
    message(STRINGS.diagnosticsSaved);
  }

  const fill = (selector, entries) => $(selector).replaceChildren(...entries.map(([value, label]) => new Option(label, value)));
  fill("#diag-step", [["", STRINGS.diagNoStep], ...Object.entries(STRINGS.diagSteps)]);
  fill("#diag-outcome", Object.entries(STRINGS.diagOutcomes));
  fill("#diag-reason", [["", STRINGS.diagNoReason], ...Object.entries(STRINGS.diagReasons)]);
  for (const [selector, action] of [["#diagnostics-export", exportReport], ["#diagnostics-browser", async () => exportFallback()]]) {
    $(selector).onclick = async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try { await action(); } finally { button.disabled = false; }
    };
  }
  const scriptError = () => { if (scriptErrors++ < 5) emit("js_error", "failed", "unexpected_js_error"); };
  window.addEventListener("error", scriptError);
  window.addEventListener("unhandledrejection", scriptError);
  emit("capabilities", "ok", "capabilities_detected", capabilities());
  return { emit, results, exportFallback, exportReport };
})();
