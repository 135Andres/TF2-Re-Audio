/* Owns microphone tracks, including requests that complete after cancellation. */
window.Recorder = class {
  constructor(onLevel, onError) {
    this.onLevel = onLevel;
    this.onError = onError;
    this.generation = 0;
    this.stream = null;
    this.media = null;
    this.context = null;
    this.audio = null;
    this.stopping = null;
  }

  async acquire(deviceId) {
    const generation = this.generation;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      throw new Error(STRINGS.microphoneUnsupported);
    }
    let expired = false;
    let timer;
    const request = navigator.mediaDevices.getUserMedia({
      audio: deviceId ? { deviceId: { exact: deviceId } } : true
    }).then(stream => {
      if (expired || generation !== this.generation) {
        stream.getTracks().forEach(track => track.stop());
        throw new Error(STRINGS.microphoneCancelled);
      }
      return stream;
    });
    try {
      return await Promise.race([request, new Promise((_, reject) => {
        timer = setTimeout(() => {
          expired = true;
          reject(new Error(STRINGS.microphoneTimeout));
        }, 15000);
      })]);
    } finally {
      clearTimeout(timer);
    }
  }

  async devices(select) {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const selected = select.value;
      select.replaceChildren(new Option(STRINGS.defaultMicrophone, ""));
      devices.filter(device => device.kind === "audioinput").forEach((device, index) => {
        select.add(new Option(device.label || `${STRINGS.microphone} ${index + 1}`, device.deviceId));
      });
      if ([...select.options].some(option => option.value === selected)) select.value = selected;
    } catch (error) {
      this.report(error);
    }
  }

  async test(deviceId) {
    this.destroy();
    try {
      this.stream = await this.acquire(deviceId);
      this.level();
      this.testTimer = setTimeout(() => this.release(), 3000);
    } catch (error) {
      this.release();
      this.report(error);
    }
  }

  async start(deviceId, onLimit) {
    this.destroy();
    this.audio = null;
    this.samples = null;
    try {
      this.stream = await this.acquire(deviceId);
      const mimeType = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"]
        .find(type => MediaRecorder.isTypeSupported(type));
      this.media = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
      this.chunks = [];
      this.media.ondataavailable = event => {
        if (event.data.size) this.chunks.push(event.data);
      };
      this.media.onerror = event => { this.report(event.error); this.destroy(); };
      this.media.start();
      Diagnostics.emit("record", "ok", "recording_started");
      this.started = performance.now();
      this.level();
      this.limitTimer = setTimeout(() => {
        if (typeof onLimit === "function") onLimit();
        else this.stop();
      }, 10000);
      return true;
    } catch (error) {
      this.release();
      this.report(error);
      return false;
    }
  }

  level() {
    this.context = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.context.createMediaStreamSource(this.stream);
    const analyser = this.context.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    const data = new Uint8Array(analyser.fftSize);
    const loop = () => {
      if (!this.stream) return;
      analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (const value of data) sum += ((value - 128) / 128) ** 2;
      this.onLevel(Math.min(1, Math.sqrt(sum / data.length) * 3));
      this.raf = requestAnimationFrame(loop);
    };
    loop();
  }

  stop(trim = false) {
    if (this.stopping) return this.stopping;
    const media = this.media;
    if (!media || media.state === "inactive") return Promise.resolve(null);
    const generation = this.generation;
    clearTimeout(this.limitTimer);
    this.stopping = new Promise(resolve => {
      media.onstop = async () => {
        this.media = null;
        try {
          const blob = new Blob(this.chunks, { type: media.mimeType });
          this.samples = await this.decode(blob);
          if (generation !== this.generation) return resolve(null);
          this.audio = this.prepare(trim);
          resolve(this.audio);
        } catch (error) {
          Diagnostics.emit("record", "failed", "decode_failed");
          this.onError(STRINGS.decodeFailed);
          resolve(null);
        }
      };
      media.stop();
      this.release(); // Do not keep tracks alive while decoding.
    }).finally(() => { this.stopping = null; });
    return this.stopping;
  }

  async decode(blob) {
    const decoder = new OfflineAudioContext(1, 1, 44100);
    const decoded = await decoder.decodeAudioData(await blob.arrayBuffer());
    const frames = Math.max(1, Math.min(441000, Math.ceil(decoded.duration * 44100)));
    const renderer = new OfflineAudioContext(1, frames, 44100);
    const source = renderer.createBufferSource();
    source.buffer = decoded;
    source.connect(renderer.destination);
    source.start();
    return (await renderer.startRendering()).getChannelData(0).slice();
  }

  prepare(trim) {
    let samples = this.samples;
    if (!samples) return null;
    if (trim) {
      let start = 0, end = samples.length;
      while (start < end && Math.abs(samples[start]) < 0.005) start++;
      while (end > start && Math.abs(samples[end - 1]) < 0.005) end--;
      // Preserve all-silent takes and a 50 ms margin around speech.
      if (start < end) samples = samples.slice(Math.max(0, start - 2205), Math.min(samples.length, end + 2205));
    }
    this.audio = encodeWav(samples, 44100);
    return this.audio;
  }

  release() {
    clearTimeout(this.testTimer);
    this.stream?.getTracks().forEach(track => track.stop());
    this.stream = null;
    cancelAnimationFrame(this.raf);
    if (this.context) this.context.close().catch(() => {});
    this.context = null;
    this.onLevel(0);
  }

  report(error) {
    const code = {
      NotAllowedError: "permission_denied", SecurityError: "permission_denied", NotFoundError: "device_missing",
      NotReadableError: "device_busy", OverconstrainedError: "device_constraint"
    }[error?.name] || { [STRINGS.microphoneTimeout]: "mic_timeout", [STRINGS.microphoneUnsupported]: "feature_unavailable" }[error?.message];
    if (error?.message !== STRINGS.microphoneCancelled) {
      Diagnostics.emit("microphone", code === "feature_unavailable" ? "unsupported" : "failed", code || "mic_unknown");
    }
    const message = {
      NotAllowedError: STRINGS.microphoneDenied, SecurityError: STRINGS.microphoneDenied,
      NotFoundError: STRINGS.microphoneMissing, NotReadableError: STRINGS.microphoneBusy,
      OverconstrainedError: STRINGS.microphoneConstraint
    }[error?.name] || error?.message || STRINGS.microphoneUnknown;
    this.onError(message);
  }

  destroy() {
    this.generation++;
    clearTimeout(this.limitTimer);
    if (this.media?.state === "recording") {
      this.media.onstop = null;
      this.media.stop();
    }
    this.media = null;
    this.release();
  }
};
