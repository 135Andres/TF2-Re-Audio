"""Validate and analyze uploaded WAV takes (16-bit PCM, mono, 44.1 kHz)."""

import math
import struct
import sys
from array import array
from dataclasses import dataclass

MAX_SECONDS = 10
MAX_BYTES = 1_000_000
RATE = 44100

SILENT_DBFS = -45.0
CLIP_FRACTION = 0.001


class InvalidWav(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class WavInfo:
    duration_s: float
    peak: float  # 0..1, relative to full scale (32768)
    rms: float  # 0..1, relative to full scale (32768)
    warnings: list[str]  # "silent", "clipping"


def _chunks(data: bytes) -> dict[bytes, bytes]:
    """Walk the RIFF chunks and return {id: payload} for fmt and data."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise InvalidWav("Not a WAV file (missing RIFF/WAVE header).")
    end = 8 + struct.unpack_from("<I", data, 4)[0]
    if end > len(data):
        raise InvalidWav("WAV file is truncated (RIFF size is larger than the file).")
    found = {}
    pos = 12
    while pos + 8 <= end:
        cid, size = struct.unpack_from("<4sI", data, pos)
        body = pos + 8
        if body + size > end:
            raise InvalidWav(f"WAV chunk {cid!r} is larger than the file.")
        if cid in (b"fmt ", b"data"):
            if cid in found:
                raise InvalidWav(f"WAV has more than one {cid.decode().strip()} chunk.")
            found[cid] = data[body:body + size]
        pos = body + size + (size & 1)  # chunks are padded to even length
    for cid in (b"fmt ", b"data"):
        if cid not in found:
            raise InvalidWav(f"WAV has no {cid.decode().strip()} chunk.")
    return found


def inspect_wav(data: bytes) -> WavInfo:
    """Validate a WAV take and measure its level. Raises InvalidWav with a readable reason."""
    if len(data) > MAX_BYTES:
        raise InvalidWav(f"File is too large ({len(data)} bytes, max {MAX_BYTES}).")
    chunks = _chunks(data)
    fmt = chunks[b"fmt "]
    if len(fmt) < 16:
        raise InvalidWav("WAV fmt chunk is too short.")
    tag, channels, rate, byte_rate, align, bits = struct.unpack_from("<HHIIHH", fmt)
    if tag != 1:
        raise InvalidWav("WAV must be uncompressed PCM.")
    if bits != 16:
        raise InvalidWav(f"WAV must be 16-bit (got {bits}-bit).")
    if channels != 1:
        raise InvalidWav(f"WAV must be mono (got {channels} channels).")
    if rate != RATE:
        raise InvalidWav(f"WAV must be {RATE} Hz (got {rate} Hz).")
    if align != 2 or byte_rate != RATE * 2:
        raise InvalidWav("WAV fmt chunk is inconsistent.")

    pcm = chunks[b"data"]
    if not pcm:
        raise InvalidWav("WAV has no audio.")
    if len(pcm) % 2:
        raise InvalidWav("WAV audio data has an odd length.")
    samples = array("h", pcm)
    if sys.byteorder == "big":
        samples.byteswap()
    n = len(samples)
    duration = n / RATE
    if duration > MAX_SECONDS:
        raise InvalidWav(f"Recording is too long ({duration:.1f} s, max {MAX_SECONDS} s).")

    peak = max(max(samples), -min(samples)) / 32768
    rms = math.sqrt(sum(s * s for s in samples) / n) / 32768
    warnings = []
    if rms == 0 or 20 * math.log10(rms) < SILENT_DBFS:
        warnings.append("silent")
    clipped = samples.count(32767) + samples.count(-32767) + samples.count(-32768)
    if clipped > CLIP_FRACTION * n:
        warnings.append("clipping")
    return WavInfo(duration, peak, rms, warnings)
