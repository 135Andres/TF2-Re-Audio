import unittest
from collections import Counter
from pathlib import Path

from tf2reaudio.catalog import CLASSES, VOICE_MENU, build

FIXTURE = Path(__file__).parent / "fixtures" / "vo_index.txt"
CATEGORIES = ["voice_menu", "pain_death", "domination", "other"]
# Real gaps in the game files: only the Medic has a "Charge ready" line.
MISSING = {(cls, "charge_ready") for cls in CLASSES if cls != "medic"}


class CatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.names = FIXTURE.read_text(encoding="utf-8").split()
        cls.cat = build(cls.names)
        cls.all = [l for c in CLASSES for l in cls.cat.lines(c)]

    def test_fixture_size(self):
        self.assertEqual(len(self.names), 12728)

    def test_every_voice_menu_command_per_class(self):
        for cls in CLASSES:
            for key, _, _ in VOICE_MENU:
                with self.subTest(cls=cls, key=key):
                    if (cls, key) in MISSING:
                        self.assertRaises(KeyError, self.cat.line, f"{cls}/{key}")
                    else:
                        self.assertTrue(self.cat.line(f"{cls}/{key}").files)

    def test_pain_and_death_per_class(self):
        for cls in CLASSES:
            self.assertEqual(len(self.cat.lines(cls, "pain_death")), 3, cls)

    def test_no_file_in_two_lines(self):
        files = Counter(f for l in self.all for f in l.files)
        self.assertEqual([f for f, n in files.items() if n > 1], [])

    def test_every_class_root_file_is_catalogued(self):
        files = {f for l in self.all for f in l.files}
        root = [n for n in self.names if n.count("/") == 2 and n.split("/")[2].split("_")[0] in CLASSES]
        self.assertEqual([n for n in root if n not in files], [])

    def test_known_lines(self):
        self.assertEqual(self.cat.line("soldier/go").files,
                         [f"sound/vo/soldier_go0{i}.mp3" for i in (1, 2, 3)])
        self.assertEqual(self.cat.line("soldier/medic").label, "MEDIC!")
        self.assertIn("sound/vo/scout_headleft01.wav", self.cat.line("scout/go_left").files)
        self.assertIn("sound/vo/soldier_paincrticialdeath01.mp3", self.cat.line("soldier/death").files)
        self.assertIn("sound/vo/soldier_dominationdemonmanupdate01.mp3",
                      self.cat.line("soldier/dominate_demoman").files)
        self.assertIn("sound/vo/scout_dominationsnp01.mp3", self.cat.line("scout/dominate_sniper").files)
        self.assertEqual(self.cat.line("heavy/revenge").category, "domination")
        # Context variants are not part of the command.
        self.assertNotIn("sound/vo/spy_cloakedspyidentify01.mp3", self.cat.line("spy/spy").files)

    def test_raw_lines_are_other(self):
        line = self.cat.line("soldier/raw/soldier_laughevil01")
        self.assertEqual((line.cls, line.category, line.files),
                         ("soldier", "other", ["sound/vo/soldier_laughevil01.mp3"]))
        # Subfolders (mvm, taunts, competitive) only appear in "other".
        self.assertEqual(self.cat.line("soldier/raw/mvm/norm/soldier_mvm_medic01").category, "other")
        self.assertEqual(self.cat.line("engineer/raw/compmode/cm_engie_gamewon_01").cls, "engineer")
        twins = self.cat.line("scout/raw/taunts/scout/scout_taunt_flip_int_07").files
        self.assertEqual(len(twins), 2)

    def test_lines_filter_and_unknown(self):
        self.assertTrue(all(l.category == "voice_menu" for l in self.cat.lines("pyro", "voice_menu")))
        self.assertEqual(self.cat.lines("pyro", "domination"), [])
        self.assertRaises(KeyError, self.cat.line, "soldier/nope")

    def test_is_vo_path(self):
        self.assertTrue(self.cat.is_vo_path("sound/vo/soldier_medic01.mp3"))
        self.assertFalse(self.cat.is_vo_path("sound/vo/soldier_medic99.mp3"))
        self.assertFalse(self.cat.is_vo_path("cfg/autoexec.cfg"))

    def test_print_counts(self):
        print()
        for cls in CLASSES:
            counts = {c: len(self.cat.lines(cls, c)) for c in CATEGORIES}
            print(f"{cls:9} " + " ".join(f"{c}={n}" for c, n in counts.items()))


class SyntheticTest(unittest.TestCase):
    def test_small_index(self):
        cat = build(["sound/vo/pyro_medic01.mp3", "sound/vo/pyro_laughevil01.mp3", "sound/vo/announcer_win.mp3"])
        self.assertEqual([l.id for l in cat.lines("pyro")], ["pyro/medic", "pyro/raw/pyro_laughevil01"])
        self.assertEqual(cat.lines("soldier"), [])


if __name__ == "__main__":
    unittest.main()
