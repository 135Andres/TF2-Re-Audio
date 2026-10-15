/* Browser-independent PCM16 WAV encoder used after OfflineAudioContext resampling. */
window.encodeWav = function (samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buffer);
  const text = (offset, value) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
  text(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); text(8, "WAVE"); text(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, "data"); view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) { const sample = Math.max(-1, Math.min(1, samples[i])); view.setInt16(44 + i * 2, sample < 0 ? sample * 32768 : sample * 32767, true); }
  return new Blob([buffer], { type: "audio/wav" });
};
