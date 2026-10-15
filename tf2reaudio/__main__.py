import argparse
import json
import platform
import re
import sys
import uuid
from pathlib import Path

from . import __version__, catalog, steam
from .audio import InvalidWav
from .game import MOD_DIR, TEST_MOD_DIR, Game
from .rcon import RconError
from .server import ServerError, run_local
from .store import Store, StoreError
from .util import atomic_write, data_dir
from .vpk import VpkError, VpkIndex

AUTHOR = "local"  # member id for takes made from the CLI
STEAM_MENU = "Steam Library > right-click Team Fortress 2 > Properties > General > Launch Options"

RCON_STATUS = {
    "connected": "connected",
    "not_running": "not reachable (TF2 is closed, or was started without the launch options)",
    "not_configured": "not set up yet (run `setup` and add the launch options in Steam)",
    "auth_failed": "TF2 rejected the password (run `setup`, copy the launch options again, restart TF2)",
}

APPLY_RESULT = {
    "sent": "Done: TF2 is reloading its sounds. Your new voice lines should play now.",
    "not_running": "TF2 is not reachable. It is closed, or it was started without the launch options "
                   "(run `setup`). Your recordings are saved; they will play the next time TF2 starts.",
    "auth_failed": "TF2 rejected the password. Run `setup`, copy the launch options into Steam again, "
                   "and restart TF2. Your recordings are saved.",
    "error": "TF2 did not answer as expected. Try again, or restart TF2 to hear your changes. "
             "Your recordings are saved.",
}


class Problem(Exception):
    """Expected problem; the message is shown to the user as is."""


def device_id() -> str:
    """This PC's device id, kept in settings.json next to the keys game.py manages."""
    path = data_dir() / "settings.json"
    try:
        settings = json.loads(path.read_bytes())
    except (OSError, ValueError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    dev = settings.get("device_id")
    if not (isinstance(dev, str) and re.fullmatch(r"[0-9a-f]{32}", dev)):
        settings["device_id"] = dev = uuid.uuid4().hex
        atomic_write(path, json.dumps(settings, indent=1, sort_keys=True).encode("utf-8"))
    return dev


def pick_tf(path) -> Path:
    """The "tf" folder from --tf, or the first usable install Steam knows about."""
    if path:
        check = steam.check_install(Path(path))
        if not check.ok:
            raise Problem(f"{check.detail}\nPass the 'Team Fortress 2' folder (or its 'tf' folder) with --tf.")
        return check.tf
    installs = steam.find_installs()
    checks = [steam.check_install(tf) for tf in installs]
    for check in checks:
        if check.ok:
            return check.tf
    if installs:
        raise Problem("TF2 was found but can't be used:\n" + "\n".join(f"  {c.detail}" for c in checks))
    raise Problem("TF2 was not found in your Steam libraries.\n"
                  'Pass its folder with --tf, for example: --tf "D:\\SteamLibrary\\steamapps\\common\\Team Fortress 2"')


def load_catalog(tf: Path):
    """(names in the voice VPK, catalog)."""
    names = VpkIndex(tf / steam.VO_VPK).names()
    return names, catalog.build(names)


def open_game(path) -> Game:
    tf = pick_tf(path)
    cat = load_catalog(tf)[1]
    dev = device_id()  # before Game, which loads settings.json and keeps this key
    return Game(tf, Store(data_dir() / "collection", dev, catalog=cat), cat)


# ---- commands ----

def cmd_doctor(args) -> int:
    lines = [
        "TF2 Re-Audio doctor report",
        f"App version: {__version__}",
        f"Python: {platform.python_version()}",
        f"OS: {platform.platform()}",
        f"Data folder: {data_dir()}",
    ]
    installs = steam.find_installs()
    lines.append(f"TF2 installs found by Steam: {len(installs)}")
    for tf in installs:
        check = steam.check_install(tf)
        lines.append(f"  - {tf}: {'OK' if check.ok else check.problem} ({check.detail})")
    if args.tf:
        check = steam.check_install(Path(args.tf))
        lines.append(f"Folder from --tf: {'OK' if check.ok else check.problem} ({check.detail})")
    ok = False
    try:
        tf = pick_tf(args.tf)
        lines.append(f"Using TF2 at: {tf}")
        names, cat = load_catalog(tf)
        lines.append(f"Voice file archive: readable ({len(names)} files)")
        lines.append(f"Voice line catalog: {sum(len(cat.lines(c)) for c in catalog.CLASSES)} lines")
        mod = "present" if (tf / "custom" / MOD_DIR).is_dir() else "not created yet"
        lines.append(f"Mod folder (custom/{MOD_DIR}): {mod}")
        store = Store(data_dir() / "collection", device_id(), catalog=cat)
        if store.warning:
            lines.append(f"Collection: {store.warning}")
        game = Game(tf, store, cat)
        test = "present (remove it with `setup --remove-test-mod`)" if game.test_mod_present() else "not present"
        lines.append(f"Phase 0 test folder (custom/{TEST_MOD_DIR}): {test}")
        status = game.status()
        lines.append(f"RCON: {RCON_STATUS.get(status, status)}")
        lines.append(f"Changes waiting for apply: {game.pending_apply()} files")
        ok = True
    except (Problem, OSError, VpkError, StoreError, RconError) as e:
        lines.append(f"Problem: {e}")
    report = "\n".join(lines) + "\n"
    print(report, end="")
    if args.copy:
        path = data_dir() / "doctor-report.txt"
        atomic_write(path, report.encode("utf-8"))
        print(f"Report saved to: {path}")
    return 0 if ok else 1


def cmd_setup(args) -> int:
    game = open_game(args.tf)
    print(f"TF2 folder: {game.tf}\n")
    print("1. Copy these launch options:\n")
    print(f"   {game.launch_options()}\n")
    print(f"2. Paste them in: {STEAM_MENU}")
    print("   Keep any options you already have; add these at the end.\n")
    print("3. Restart TF2 so it uses them. TF2 only loads new mod folders when it starts,")
    print("   so also restart it once after your first import creates the mod folder.")
    if game.test_mod_present():
        if args.remove_test_mod:
            game.remove_test_mod()
            print(f"\nRemoved the Phase 0 test folder (custom/{TEST_MOD_DIR}).")
        else:
            print(f"\nThe Phase 0 test folder (custom/{TEST_MOD_DIR}) is still installed and can hide your "
                  "recordings. Remove it with: setup --remove-test-mod")
    return 0


def cmd_import_wav(args) -> int:
    game = open_game(args.tf)
    try:
        game.catalog.line(args.line_id.partition("#")[0])
    except KeyError:
        raise Problem(f"Unknown voice line: {args.line_id!r}. Run `lines CLASS` (for example `lines soldier`) "
                      "to see the line ids.") from None
    try:
        data = Path(args.file).read_bytes()
    except OSError as e:
        raise Problem(f"Can't read {args.file}: {e.strerror or e}") from None
    try:
        take = game.store.add_take(args.line_id, data, AUTHOR)
    except InvalidWav as e:
        raise Problem(f"This WAV can't be used: {e.reason}\n"
                      "It must be 16-bit PCM, mono, 44100 Hz and at most 10 seconds.") from None
    game.store.set_active(args.line_id, take)
    created = not game.mod.exists()
    written = game.sync_files()
    print(f"Saved the recording for {args.line_id}.")
    print(f"Wrote {written} file(s) in {game.mod}")
    if created and game.mod.exists():
        print("The mod folder was just created. If TF2 is running, restart it once: "
              "it only loads new mod folders at startup.")
    print("Run `apply` (or restart TF2) to hear it.")
    return 0


def cmd_apply(args) -> int:
    result = open_game(args.tf).apply()
    print(APPLY_RESULT[result])
    return 0 if result == "sent" else 1


def cmd_run(args) -> int:
    """Start the local application, reusing a running instance when possible."""
    return run_local(Path(args.tf) if args.tf else None, args.port, browser=not args.no_browser)


def cmd_host(args) -> int:
    print("Group hosting is not available yet. Use `run` for the local app.", file=sys.stderr)
    return 1


def cmd_lines(args) -> int:
    found = load_catalog(pick_tf(args.tf))[1].lines(args.cls, args.category)
    width = max((len(line.id) for line in found), default=0)
    for line in found:
        print(f"{line.id:<{width}}  {line.label}  ({line.category}, {len(line.files)} files)")
    if not found:
        print(f"No lines found for {args.cls}.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tf2reaudio", description="TF2 Re-Audio")
    parser.add_argument("--version", action="version", version=f"TF2 Re-Audio {__version__}")
    sub = parser.add_subparsers(dest="command")
    tf_help = "TF2 folder to use (default: the first one found through Steam)"
    p = sub.add_parser("run", help="Start the local app and open it in your browser")
    p.add_argument("--tf", help=tf_help)
    p.add_argument("--port", type=int, default=8440, help="local HTTP port (default: 8440)")
    p.add_argument("--no-browser", action="store_true", help="print the local URL without opening a browser")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("host", help="Start the local app; group hosting is added later")
    p.add_argument("--tf", help=tf_help)
    p.add_argument("--port", type=int, default=8440, help="local HTTP port (default: 8440)")
    p.set_defaults(func=cmd_host)
    p = sub.add_parser("doctor", help="Check your setup and print a report (no passwords)")
    p.add_argument("--tf", help=tf_help)
    p.add_argument("--copy", action="store_true", help="also save the report to a text file")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("setup", help="Show the Steam launch options and how to add them")
    p.add_argument("--tf", help=tf_help)
    p.add_argument("--remove-test-mod", action="store_true", help=f"remove the custom/{TEST_MOD_DIR} test folder")
    p.set_defaults(func=cmd_setup)

    p = sub.add_parser("import-wav", help="Use a WAV file as a voice line")
    p.add_argument("line_id", metavar="LINE_ID", help="for example soldier/medic (see `lines`)")
    p.add_argument("file", metavar="FILE.wav")
    p.add_argument("--tf", help=tf_help)
    p.set_defaults(func=cmd_import_wav)

    p = sub.add_parser("apply", help="Ask TF2 to reload sounds so changes play now")
    p.add_argument("--tf", help=tf_help)
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("lines", help="List the voice line ids of a class")
    p.add_argument("cls", metavar="CLASS", choices=catalog.CLASSES, help=", ".join(catalog.CLASSES))
    p.add_argument("--category", choices=["voice_menu", "pain_death", "domination", "other"])
    p.add_argument("--tf", help=tf_help)
    p.set_defaults(func=cmd_lines)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (Problem, ServerError, VpkError, StoreError, RconError) as e:
        print(f"Error: {e}", file=sys.stderr)
    except OSError as e:
        print(f"Error: {e.strerror or e}{f' ({e.filename})' if e.filename else ''}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
