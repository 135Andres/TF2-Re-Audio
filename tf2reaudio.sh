#!/bin/sh
# TF2 Re-Audio launcher for Linux. Run it from a terminal or double-click it.
# Needs python3 >= 3.10 (standard library only).

here=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1

# Double-clicked with no terminal: reopen inside one so messages are visible.
# "sh <path>" keeps it two or more arguments, so terminals never re-split a path with spaces.
if [ ! -t 0 ] && [ ! -t 1 ] && [ -z "$TF2REAUDIO_IN_TERMINAL" ] && [ -n "$DISPLAY$WAYLAND_DISPLAY" ]; then
    export TF2REAUDIO_IN_TERMINAL=1
    for t in "x-terminal-emulator -e" "gnome-terminal --" "konsole -e" "xfce4-terminal -x" "xterm -e"; do
        # shellcheck disable=SC2086 # $t is "terminal flag" on purpose
        command -v "${t%% *}" >/dev/null 2>&1 && exec $t sh "$here/tf2reaudio.sh" "$@"
    done
fi

fail() {
    echo
    echo "$@"
    # Keep a terminal we opened ourselves from closing before the user reads the error.
    if [ -n "$TF2REAUDIO_IN_TERMINAL" ]; then
        printf 'Press Enter to close this window.'
        read -r _
    fi
    exit 1
}

install_hint() {
    # shellcheck disable=SC1091
    ids=$( . /etc/os-release 2>/dev/null; echo "$ID $ID_LIKE" )
    case " $ids " in
        *" arch "*) echo "  sudo pacman -S python" ;;
        *" debian "* | *" ubuntu "*) echo "  sudo apt install python3" ;;
        *" fedora "* | *" rhel "*) echo "  sudo dnf install python3" ;;
        *) echo "  Install Python 3.10 or newer with your distribution's package manager." ;;
    esac
}

cd "$here" || fail "ERROR [BOOT_FOLDER]: Could not open the folder of this launcher: $here"
[ -f tf2reaudio/__main__.py ] || fail "ERROR [BOOT_NOT_EXTRACTED]: The \"tf2reaudio\" folder was not found next to tf2reaudio.sh.
Extract the whole ZIP first, then run tf2reaudio.sh from the extracted folder."

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then
        msg="ERROR [BOOT_PYTHON_MISSING]: TF2 Re-Audio needs Python 3.10 or newer, but python3 is $(python3 -V 2>&1).
Update Python (or your distribution), for example:"
    else
        msg="ERROR [BOOT_PYTHON_MISSING]: Python 3 was not found. Install it, for example:"
    fi
    fail "$msg
$(install_hint)
Then run tf2reaudio.sh again."
fi

# No arguments (double-click) = "run"; otherwise pass them through, e.g. "./tf2reaudio.sh doctor".
[ "$#" -eq 0 ] && set -- run
python3 -m tf2reaudio "$@"
rc=$?
[ "$rc" -eq 0 ] || fail "ERROR [BOOT_APP_EXIT]: TF2 Re-Audio stopped with error code $rc. Read the message above.
For help, run \"sh tf2reaudio.sh doctor --bundle\" and send the ZIP it creates."
