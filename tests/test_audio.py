import io
import math
import struct
import unittest
import wave

from tf2reaudio.audio import MAX_BYTES, RATE, InvalidWav, inspect_wav


def pcm(samples) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def tone(seconds=0.5, amp=10000):
    return [int(amp * math.sin(2 * math.pi * 440 * i / RATE)) for i in range(int(seconds * RATE))]


def chunk(cid: bytes, body: bytes) -> bytes:
    return struct.pack("<4sI", cid, len(body)) + body + b"\0" * (len(body) & 1)


def fmt(tag=1, channels=1, rate=RATE, bits=16) -> bytes:
    align = channels * bits // 8
    return chunk(b"fmt ", struct.pack("<HHIIHH", tag, channels, rate, rate * align, align, bits))


def riff(*chunks: bytes) -> bytes:
    body = b"WAVE" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def wav(samples=None, **kw) -> bytes:
    return riff(fmt(**kw), chunk(b"data", pcm(tone() if samples is None else samples)))


def wave_module(channels=1, rate=RATE, width=2, frames=b"\0\1" * 1000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(frames)
    return buf.getvalue()


class ValidTest(unittest.TestCase):
    def test_valid_tone(self):
        info = inspect_wav(wav())
        self.assertAlmostEqual(info.duration_s, 0.5)
        self.assertAlmostEqual(info.peak, 10000 / 32768, places=3)
        self.assertAlmostEqual(info.rms, 10000 / 32768 / math.sqrt(2), places=3)
        self.assertEqual(info.warnings, [])

    def test_written_by_wave_module(self):
        info = inspect_wav(wave_module(frames=pcm(tone(1.0))))
        self.assertAlmostEqual(info.duration_s, 1.0)

    def test_tolerates_list_and_odd_padding(self):
        data = riff(chunk(b"LIST", b"INFOabc"), fmt(), chunk(b"junk", b"x"), chunk(b"data", pcm(tone())))
        self.assertEqual(inspect_wav(data).warnings, [])

    def test_exactly_max_seconds(self):
        self.assertAlmostEqual(inspect_wav(wav([100] * (RATE * 10))).duration_s, 10.0)


class WarningsTest(unittest.TestCase):
    def test_digital_silence(self):
        info = inspect_wav(wav([0] * 1000))
        self.assertEqual(info.warnings, ["silent"])
        self.assertEqual(info.rms, 0)

    def test_quiet_is_silent(self):
        # amplitude 100 -> about -50 dBFS RMS
        self.assertIn("silent", inspect_wav(wav(tone(amp=100))).warnings)

    def test_moderate_is_not_silent(self):
        # amplitude 300 -> about -40.8 dBFS RMS
        self.assertNotIn("silent", inspect_wav(wav(tone(amp=300))).warnings)

    def test_clipping(self):
        samples = tone()
        samples[:100] = [32767, -32768] * 50
        info = inspect_wav(wav(samples))
        self.assertEqual(info.warnings, ["clipping"])
        self.assertEqual(info.peak, 1.0)

    def test_few_clipped_samples_ok(self):
        samples = tone()
        samples[:5] = [32767] * 5  # 5 of 22050 is below 0.1 %
        self.assertEqual(inspect_wav(wav(samples)).warnings, [])


class RejectTest(unittest.TestCase):
    def assertRejects(self, data: bytes, fragment: str):
        with self.assertRaises(InvalidWav) as cm:
            inspect_wav(data)
        self.assertIn(fragment, cm.exception.reason)

    def test_not_riff(self):
        self.assertRejects(b"ID3\x04" + b"\0" * 100, "RIFF")
        self.assertRejects(b"", "RIFF")
        self.assertRejects(b"RIFF\4\0\0\0AVI ", "RIFF")

    def test_stereo(self):
        self.assertRejects(wave_module(channels=2), "mono")

    def test_48k(self):
        self.assertRejects(wave_module(rate=48000), "44100")

    def test_8bit(self):
        self.assertRejects(wave_module(width=1, frames=b"\x80" * 100), "16-bit")

    def test_not_pcm(self):
        self.assertRejects(wav(tag=3), "PCM")
        self.assertRejects(wav(tag=0xFFFE), "PCM")

    def test_inconsistent_fmt(self):
        body = struct.pack("<HHIIHH", 1, 1, RATE, 12345, 2, 16)
        self.assertRejects(riff(chunk(b"fmt ", body), chunk(b"data", pcm(tone()))), "inconsistent")

    def test_short_fmt(self):
        self.assertRejects(riff(chunk(b"fmt ", b"\1\0\1\0"), chunk(b"data", pcm(tone()))), "too short")

    def test_empty_data(self):
        self.assertRejects(wav([]), "no audio")

    def test_odd_data(self):
        self.assertRejects(riff(fmt(), chunk(b"data", pcm(tone()) + b"\0")), "odd")

    def test_too_long(self):
        self.assertRejects(wav([0] * (RATE * 10 + 1)), "too long")

    def test_too_many_bytes(self):
        self.assertRejects(wav() + b"\0" * MAX_BYTES, "too large")

    def test_missing_chunks(self):
        self.assertRejects(riff(fmt()), "no data")
        self.assertRejects(riff(chunk(b"data", pcm(tone()))), "no fmt")

    def test_duplicate_chunks(self):
        self.assertRejects(riff(fmt(), fmt(), chunk(b"data", pcm(tone()))), "more than one")

    def test_truncated(self):
        good = wav()
        for cut in (8, 20, 40, len(good) // 2, len(good) - 1):
            with self.subTest(cut=cut):
                with self.assertRaises(InvalidWav):
                    inspect_wav(good[:cut])

    def test_chunk_size_lies(self):
        good = wav()
        # data chunk claims more bytes than exist, RIFF size left consistent with the file
        data_pos = good.index(b"data")
        bad = good[:data_pos + 4] + struct.pack("<I", 0xFFFFFFF0) + good[data_pos + 8:]
        self.assertRejects(bad, "larger than the file")

    def test_riff_size_lies(self):
        good = wav()
        self.assertRejects(good[:4] + struct.pack("<I", 0xFFFFFFFF) + good[8:], "truncated")

    def test_garbage_never_crashes(self):
        import random

        rng = random.Random(1)
        good = wav(tone(0.01))
        for _ in range(500):
            data = bytearray(good)
            for _ in range(rng.randint(1, 8)):
                data[rng.randrange(len(data))] = rng.randrange(256)
            try:
                inspect_wav(bytes(data[: rng.randint(0, len(data))]))
            except InvalidWav:
                pass


if __name__ == "__main__":
    unittest.main()
