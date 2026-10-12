import argparse
import sys

from . import __version__


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tf2reaudio", description="TF2 Re-Audio")
    parser.add_argument("--version", action="version", version=f"TF2 Re-Audio {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="Start the app and open it in your browser")
    sub.add_parser("doctor", help="Check your setup and print a report")
    sub.add_parser("host", help="Run the app and host your group")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    print("Not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
