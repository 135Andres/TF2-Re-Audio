"""Catalog of class voice lines: maps logical lines (e.g. "soldier/medic") to VPK file paths."""

import re
from dataclasses import dataclass

CLASSES = ["scout", "soldier", "pyro", "demoman", "heavy", "engineer", "medic", "sniper", "spy"]

# (key, label, filename stem regex). A file matches "sound/vo/<class>_<stem><digits>.<mp3|wav>".
# Only the generic variant of each command is listed; context variants (cloakedspyidentify,
# helpmecapture, thanksfortheheal, ...) stay as raw lines in "other".
VOICE_MENU = [
    ("medic", "MEDIC!", "medic"),
    ("thanks", "Thanks!", "thanks"),
    ("go", "Go! Go! Go!", "go"),
    ("move_up", "Move up!", "moveup"),
    ("go_left", "Go left", "headleft"),
    ("go_right", "Go right", "headright"),
    ("yes", "Yes", "yes"),
    ("no", "No", "no"),
    ("incoming", "Incoming", "incoming"),
    ("spy", "Spy!", "cloakedspy"),
    ("sentry_ahead", "Sentry ahead!", "sentryahead"),
    ("teleporter_here", "Teleporter here", "needteleporter"),
    ("dispenser_here", "Dispenser here", "needdispenser"),
    ("sentry_here", "Sentry here", "needsentry"),
    ("activate_charge", "Activate charge!", "activatecharge"),
    ("charge_ready", "ÜberCharge ready", "autochargeready"),  # only the Medic has it
    ("help", "Help!", "helpme"),
    ("battle_cry", "Battle cry", "battlecry"),
    ("cheers", "Cheers", "cheers"),
    ("jeers", "Jeers", "jeers"),
    ("positive", "Positive", "positivevocalization"),
    ("negative", "Negative", "negativevocalization"),
    ("nice_shot", "Nice shot", "niceshot"),
    ("good_job", "Good job", "goodjob"),
]

PAIN_DEATH = [
    ("pain_sharp", "Pain (sharp)", "painsharp"),
    ("pain_severe", "Pain (severe)", "painsevere"),
    ("death", "Death scream", "paincrticialdeath"),  # "crticial" is Valve's spelling
]

# Victim names vary: full ("dominationsniper"), Scout's short form ("dominationsnp") and typos/updates.
DOMINATION = [
    ("domination", "Domination", "domination"),
    ("dominate_scout", "Dominating a Scout", "domination(?:scout|sct)"),
    ("dominate_soldier", "Dominating a Soldier", "domination(?:soldier|sol)(?:update)?"),
    ("dominate_pyro", "Dominating a Pyro", "domination(?:pyro|pyr)"),
    ("dominate_demoman", "Dominating a Demoman", "domination(?:demoman|demonman|dem)(?:update)?"),
    ("dominate_heavy", "Dominating a Heavy", "domination(?:heavy|hvy)"),
    ("dominate_engineer", "Dominating an Engineer", "domination(?:engineer|eng)"),
    ("dominate_medic", "Dominating a Medic", "domination(?:medic|med)"),
    ("dominate_sniper", "Dominating a Sniper", "domination(?:sniper|snp)"),
    ("dominate_spy", "Dominating a Spy", "dominationspy"),
    ("revenge", "Revenge", "revenge"),
]

TABLES = [("voice_menu", VOICE_MENU), ("pain_death", PAIN_DEATH), ("domination", DOMINATION)]

# Filename prefixes used outside sound/vo/<class>_* (taunts, competitive mode, quests).
_ALIASES = {**{c: c for c in CLASSES}, "demo": "demoman", "eng": "engineer", "engie": "engineer"}
_CLS = "|".join(CLASSES)
_RULES = [
    (re.compile(rf"sound/vo/({_CLS})_{stem}\d+\.(?:mp3|wav)"), category, key, label)
    for category, table in TABLES
    for key, label, stem in table
]


@dataclass
class Line:
    id: str
    cls: str
    label: str
    category: str
    files: list[str]


def _owner(path: str) -> str | None:
    """Class that voices a file outside the curated tables, from its filename prefix."""
    name = path.rsplit("/", 1)[-1].removeprefix("cm_")
    return _ALIASES.get(name.split("_", 1)[0]) if "_" in name else None


class Catalog:
    def __init__(self, lines: list[Line], names: set[str]):
        self._lines = {line.id: line for line in lines}
        self._names = names

    def lines(self, cls: str, category: str | None = None) -> list[Line]:
        return [l for l in self._lines.values() if l.cls == cls and category in (None, l.category)]

    def line(self, line_id: str) -> Line:
        return self._lines[line_id]

    def is_vo_path(self, path: str) -> bool:
        return path in self._names


def build(names: list[str]) -> Catalog:
    names = sorted(set(names))
    found = {}  # line id -> Line, in table order first, then raw lines
    for _, category, key, label in _RULES:
        for cls in CLASSES:
            found[f"{cls}/{key}"] = Line(f"{cls}/{key}", cls, label, category, [])
    raw = []
    for name in names:
        for rx, category, key, label in _RULES:
            if m := rx.fullmatch(name):
                found[f"{m[1]}/{key}"].files.append(name)
                break
        else:
            if name.startswith("sound/vo/") and (cls := _owner(name)):
                raw.append((cls, name))
    lines = [l for l in found.values() if l.files]
    by_id = {}
    for cls, name in raw:
        rel = name.removeprefix("sound/vo/").rsplit(".", 1)[0]  # .mp3 and .wav twins share one line
        line_id = f"{cls}/raw/{rel}"
        if line_id not in by_id:
            by_id[line_id] = Line(line_id, cls, rel.rsplit("/", 1)[-1], "other", [])
        by_id[line_id].files.append(name)
    return Catalog(lines + list(by_id.values()), set(names))
