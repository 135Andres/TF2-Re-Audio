import array
import functools
import math
import shutil
import struct
import subprocess
import unittest
from fractions import Fraction

from tf2reaudio import mp3
from tf2reaudio.mp3_tables import HUFFMAN
from tests.test_store import wav

RATE = 44100


@functools.lru_cache(maxsize=None)
def _encoded(data: bytes) -> bytes:
    return mp3.encode(data)


def as_installed(rel: str, data: bytes) -> bytes:
    """The bytes the game bridge installs for a take: .mp3 voice files are MP3-encoded."""
    return _encoded(data) if rel.endswith(".mp3") else data


def pcm_wav(samples, channels=1, width=2, rate=RATE) -> bytes:
    pcm = struct.pack(f"<{len(samples)}h", *samples) if width == 2 else bytes(len(samples))
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, channels, rate, rate * channels * width, channels * width, 8 * width)
    body = b"WAVE" + fmt + struct.pack("<4sI", b"data", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


def frames(data: bytes) -> list[bytes]:
    out, at = [], 0
    while at < len(data):
        header = int.from_bytes(data[at:at + 4], "big")
        assert header >> 21 == 0x7FF, f"lost frame sync at byte {at}"
        size = 144 * 128000 // RATE + (header >> 9 & 1)
        out.append(data[at:at + size])
        at += size
    return out


def tone(seconds, freq=440, level=8000):
    return [int(level * math.sin(2 * math.pi * freq * i / RATE)) for i in range(int(RATE * seconds))]


class EncoderTest(unittest.TestCase):
    def test_frames_are_mpeg1_layer3_mono_128k(self):
        data = mp3.encode(wav())
        found = frames(data)
        # 0.1 s of audio plus one flush frame
        self.assertEqual(len(found), math.ceil((RATE // 10 + 1152) / 1152))
        for frame in found:
            header = int.from_bytes(frame[:4], "big")
            self.assertEqual(header >> 17 & 0xF, 0b1101)  # MPEG-1, Layer III, no CRC
            self.assertEqual(header >> 12 & 0xF, 9)  # 128 kbit/s
            self.assertEqual(header >> 10 & 0x3, 0)  # 44.1 kHz
            self.assertEqual(header >> 6 & 0x3, 3)  # mono
            self.assertIn(len(frame), (417, 418))

    def test_part2_3_lengths_fit_the_frame(self):
        for frame in frames(mp3.encode(pcm_wav(tone(0.5, 3000, 30000)))):
            side = int.from_bytes(frame[4:21], "big")
            first, second = side >> 106 & 0xFFF, side >> 47 & 0xFFF
            self.assertEqual(side >> 127, 0)  # main_data_begin: no reservoir
            self.assertLessEqual(first + second, (len(frame) - 21) * 8)

    def test_silence_and_empty_input(self):
        self.assertEqual(len(frames(mp3.encode(pcm_wav([0] * 5000)))), 6)
        self.assertEqual(len(frames(mp3.encode(pcm_wav([])))), 1)

    def test_rejects_other_formats(self):
        for bad in (pcm_wav([0] * 100, channels=2), pcm_wav([0] * 100, rate=48000), pcm_wav([0] * 100, width=1),
                    b"not a wav"):
            with self.assertRaises(mp3.Mp3Error):
                mp3.encode(bad)

    def test_huffman_tables_are_complete_prefix_codes(self):
        for table in {id(h[3]): h for h in HUFFMAN if h}.values():
            codes = [format(c, f"0{n}b") for c, n in zip(table[3], table[4])]
            self.assertEqual(sum(Fraction(1, 2 ** n) for n in table[4]), 1)
            self.assertFalse(any(a != b and b.startswith(a) for a in codes for b in codes))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is optional; used only to check decoding")
    def test_decodes_back_to_the_input(self):
        source = tone(1.0, 440, 12000)
        out = subprocess.run(["ffmpeg", "-v", "error", "-err_detect", "explode", "-f", "mp3", "-i", "-",
                              "-f", "s16le", "-"], input=mp3.encode(pcm_wav(source)), capture_output=True, check=True)
        decoded = array.array("h", out.stdout)
        delay = 1057  # encoder filterbank plus decoder delay
        pairs = list(zip(source[2000:40000], decoded[2000 + delay:40000 + delay]))
        signal = sum(a * a for a, _ in pairs)
        noise = sum((a - b) ** 2 for a, b in pairs)
        self.assertGreater(10 * math.log10(signal / noise), 40)


if __name__ == "__main__":
    unittest.main()
