"""Pure-Python MPEG-1 Layer III encoder for the app's voice takes.

TF2 decodes a voice file by its extension, so a take installed as ".mp3" must be real MP3
(a WAV renamed to .mp3 plays as silence). Takes are short (<= 10 s), mono, 16-bit, 44.1 kHz.
The encoder follows ISO/IEC 11172-3 with the simplifications of the shine encoder: long
blocks only, no psychoacoustic model, no scalefactors and no bit reservoir, at 128 kbit/s.
"""

import array
import io
import math
import sys
import wave
from operator import mul

from .mp3_tables import HUFFMAN, WINDOW

RATE = 44100
BITRATE = 128
GRANULE = 576
FRAME = 2 * GRANULE
_FRAME_BITS = 144 * BITRATE * 1000  # frame length in bytes is this / RATE
_HEADER_BITS = 32
_SIDE_BITS = 136  # MPEG-1 mono side information
_LIMIT = 8191 + 15  # largest value the escape tables can code
# Scalefactor band starts for long blocks at 44.1 kHz (Table B.8)
_SFB = (0, 4, 8, 12, 16, 20, 24, 30, 36, 44, 52, 62, 74, 90, 110, 134, 162, 196, 238, 288, 342, 418, 576)
# Big-values region split for each number of scalefactor bands (from shine)
_SUBDIVIDE = ((0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 1), (1, 1), (1, 1), (1, 2), (2, 2), (2, 3), (2, 3),
              (3, 4), (3, 4), (3, 4), (4, 5), (4, 5), (4, 6), (5, 6), (5, 6), (5, 7), (6, 7), (6, 7))
_FILTER = [[math.cos((2 * i + 1) * (16 - k) * math.pi / 64) for k in range(64)] for i in range(32)]
_MDCT = [[math.sin(math.pi / 36 * (k + 0.5)) * math.cos(math.pi / 72 * (2 * k + 19) * (2 * m + 1)) for k in range(36)]
         for m in range(18)]
_ALIAS = [(1 / math.sqrt(1 + c * c), c / math.sqrt(1 + c * c))
          for c in (-0.6, -0.535, -0.33, -0.185, -0.095, -0.041, -0.0142, -0.0037)]  # (cs, ca), Table B.9
# 16-bit PCM to [-1, 1), divided by the MDCT's N/4 = 9 gain so the decoder outputs the input level.
_SCALE = 1 / (9 * 32768)


class Mp3Error(ValueError):
    pass


def encode(wav_bytes: bytes) -> bytes:
    """Encode a mono 16-bit 44.1 kHz WAV into MP3 bytes."""
    try:
        with wave.open(io.BytesIO(wav_bytes)) as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
                raise Mp3Error("MP3 conversion needs a mono 16-bit 44.1 kHz WAV.")
            pcm = array.array("h", w.readframes(w.getnframes()))
    except (wave.Error, EOFError) as e:
        raise Mp3Error(f"Could not read the WAV for MP3 conversion: {e}") from None
    if sys.byteorder == "big":
        pcm.byteswap()
    # One extra frame flushes the filterbank delay so the end of the take is kept.
    samples = [s * _SCALE for s in pcm] + [0.0] * (FRAME + (-len(pcm)) % FRAME)
    history = [0.0] * 512
    previous = [[0.0] * 32 for _ in range(18)]
    out = bytearray()
    for n, start in enumerate(range(0, len(samples), FRAME)):
        frame_bytes = (n + 1) * _FRAME_BITS // RATE - n * _FRAME_BITS // RATE
        budget = (frame_bytes * 8 - _HEADER_BITS - _SIDE_BITS) // 2
        granules = []
        for g in range(2):
            subbands = []
            for k in range(18):
                at = start + g * GRANULE + k * 32
                history = samples[at:at + 32][::-1] + history[:480]
                subbands.append(_analyse(history, odd=k % 2))
            granules.append(_quantize_granule(_mdct(previous, subbands), budget))
            previous = subbands
        out += _frame(granules, frame_bytes)
    return bytes(out)


def _analyse(history, odd):
    """Polyphase filterbank: 32 subband samples from the newest 512 input samples (newest first)."""
    z = list(map(mul, history, WINDOW))
    y = [sum(z[i::64]) for i in range(64)]
    s = [sum(map(mul, row, y)) for row in _FILTER]
    if odd:  # the hybrid filterbank expects odd subbands inverted at odd time steps
        s[1::2] = [-v for v in s[1::2]]
    return s


def _mdct(previous, current):
    """18-line MDCT per subband over two granules, then the alias-reduction butterflies."""
    xr = []
    for band in range(32):
        block = [row[band] for row in previous] + [row[band] for row in current]
        xr += [sum(map(mul, coefs, block)) for coefs in _MDCT]
    for band in range(18, GRANULE, 18):
        for i, (cs, ca) in enumerate(_ALIAS):
            hi, lo = xr[band + i], xr[band - 1 - i]
            xr[band + i] = hi * cs - lo * ca
            xr[band - 1 - i] = lo * cs + hi * ca
    return xr


def _quantize(magnitudes, step):
    scale = 2 ** (-step / 4)
    return [int((a * scale) ** 0.75 + 0.4054) for a in magnitudes]  # nint(x**0.75 - 0.0946)


def _quantize_granule(xr, budget):
    magnitudes = [abs(v) for v in xr]
    if not any(magnitudes):
        return {"step": 0, "ix": [0] * GRANULE, "xr": xr, **_layout([0] * GRANULE)}

    def attempt(step):
        ix = _quantize(magnitudes, step)
        if max(ix) > _LIMIT:
            return None
        layout = _layout(ix)
        return layout if layout["bits"] <= budget else None

    # Smallest step size (finest quantization) whose code fits the granule's bits.
    lo, hi = -120, 45
    while lo < hi:
        mid = (lo + hi) // 2
        if attempt(mid):
            hi = mid
        else:
            lo = mid + 1
    while not attempt(lo):  # bit counts are not strictly monotonic
        lo += 1
    ix = _quantize(magnitudes, lo)
    return {"step": lo, "ix": ix, "xr": xr, **_layout(ix)}


def _layout(ix):
    """Regions, Huffman tables and bit count for one granule of quantized values."""
    i = GRANULE
    while i > 1 and not ix[i - 1] and not ix[i - 2]:
        i -= 2
    count1 = 0
    while i > 3 and max(ix[i - 4:i]) <= 1:
        i -= 4
        count1 += 1
    big_values = i // 2
    end = 2 * big_values
    sum_a = sum_b = 0
    for j in range(end, end + 4 * count1, 4):
        v, w, x, y = ix[j:j + 4]
        # Table A/B index has v as the high bit (ISO order; shine reverses it).
        p = 8 * v + 4 * w + 2 * x + y
        signs = v + w + x + y
        sum_a += HUFFMAN[32][4][p] + signs
        sum_b += HUFFMAN[33][4][p] + signs
    count1_table = 0 if sum_a < sum_b else 1
    bits = min(sum_a, sum_b)
    region0 = region1 = 0
    address1 = address2 = 0
    if big_values:
        bands = 0
        while _SFB[bands] < end:
            bands += 1
        region0 = _SUBDIVIDE[bands][0]
        while region0 and _SFB[region0 + 1] > end:
            region0 -= 1
        address1 = _SFB[region0 + 1]
        region1 = _SUBDIVIDE[bands][1]
        while region1 and _SFB[region0 + region1 + 2] > end:
            region1 -= 1
        address2 = _SFB[region0 + region1 + 2]
        # With zero counts a region can start past the big values; the decoder never reads those pairs.
        address1, address2 = min(address1, end), min(address2, end)
    tables = []
    for a, b in ((0, address1), (address1, address2), (address2, end)):
        table = _choose_table(ix, a, b) if b > a else 0
        tables.append(table)
        bits += _count_bits(ix, a, b, table)
    return {"big_values": big_values, "count1": count1, "count1_table": count1_table, "tables": tables,
            "region0": region0, "region1": region1, "address1": address1, "address2": address2, "bits": bits}


def _choose_table(ix, start, end):
    top = max(ix[start:end])
    if not top:
        return 0
    if top < 15:
        candidates = [t for t in range(1, 16) if HUFFMAN[t] and HUFFMAN[t][0] > top]
    else:
        candidates = [next(t for t in group if (1 << HUFFMAN[t][2]) - 1 >= top - 15)
                      for group in (range(16, 24), range(24, 32))]
    return min(candidates, key=lambda t: _count_bits(ix, start, end, t))


def _count_bits(ix, start, end, table):
    if not table:
        return 0
    _, ylen, linbits, _, lengths = HUFFMAN[table]
    bits = 0
    for j in range(start, end, 2):
        x, y = ix[j], ix[j + 1]
        if table > 15:
            if x > 14:
                x = 15
                bits += linbits
            if y > 14:
                y = 15
                bits += linbits
        bits += lengths[x * ylen + y] + (x > 0) + (y > 0)
    return bits


class _Bits:
    def __init__(self):
        self.value = 0
        self.count = 0

    def put(self, value, n):
        self.value = (self.value << n) | (value & ((1 << n) - 1))
        self.count += n


def _frame(granules, frame_bytes):
    bits = _Bits()
    padding = frame_bytes * RATE > _FRAME_BITS
    # sync, MPEG-1, Layer III, no CRC, 128 kbit/s, 44.1 kHz, padding, private, mono, ext, (c), original, emphasis
    for value, n in ((0x7FF, 11), (3, 2), (1, 2), (1, 1), (9, 4), (0, 2), (padding, 1), (0, 1), (3, 2), (0, 2),
                     (0, 1), (1, 1), (0, 2)):
        bits.put(value, n)
    bits.put(0, 9)  # main_data_begin: no bit reservoir
    bits.put(0, 5)  # private bits
    bits.put(0, 4)  # scfsi
    for g in granules:
        bits.put(g["bits"], 12)  # part2_3_length (no scalefactor bits)
        bits.put(g["big_values"], 9)
        bits.put(g["step"] + 210, 8)  # global_gain
        bits.put(0, 4)  # scalefac_compress
        bits.put(0, 1)  # window_switching_flag: long blocks
        for table in g["tables"]:
            bits.put(table, 5)
        bits.put(g["region0"], 4)
        bits.put(g["region1"], 3)
        bits.put(0, 1)  # preflag
        bits.put(0, 1)  # scalefac_scale
        bits.put(g["count1_table"], 1)
    for g in granules:
        _huffman(bits, g)
    bits.put(0, frame_bytes * 8 - bits.count)  # ancillary padding up to the frame size
    return bits.value.to_bytes(frame_bytes, "big")


def _huffman(bits, g):
    ix = [-v if x < 0 else v for v, x in zip(g["ix"], g["xr"])]
    end = 2 * g["big_values"]
    for j in range(0, end, 2):
        table = g["tables"][(j >= g["address1"]) + (j >= g["address2"])]
        if table:
            _pair(bits, table, ix[j], ix[j + 1])
    _, _, _, codes, lengths = HUFFMAN[32 + g["count1_table"]]
    for j in range(end, end + 4 * g["count1"], 4):
        quad = ix[j:j + 4]
        v, w, x, y = (abs(q) for q in quad)
        p = 8 * v + 4 * w + 2 * x + y
        bits.put(codes[p], lengths[p])
        for q in quad:
            if q:
                bits.put(q < 0, 1)


def _pair(bits, table, x, y):
    _, ylen, linbits, codes, lengths = HUFFMAN[table]
    ax, ay = abs(x), abs(y)
    if table > 15:
        cx, cy = min(ax, 15), min(ay, 15)
        bits.put(codes[cx * ylen + cy], lengths[cx * ylen + cy])
        if ax > 14:
            bits.put(ax - 15, linbits)
        if ax:
            bits.put(x < 0, 1)
        if ay > 14:
            bits.put(ay - 15, linbits)
        if ay:
            bits.put(y < 0, 1)
    else:
        bits.put(codes[ax * ylen + ay], lengths[ax * ylen + ay])
        if ax:
            bits.put(x < 0, 1)
        if ay:
            bits.put(y < 0, 1)
