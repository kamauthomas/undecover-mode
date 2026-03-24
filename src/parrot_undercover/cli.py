from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
from typing import Any

from parrot_undercover.core import UndercoverError, UndercoverMode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parrot-undercover",
        description="Toggle a Windows-style undercover mode on Parrot OS Plasma.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for info, -vv for debug).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    enable_parser = subparsers.add_parser("enable", help="Enable undercover mode.")
    enable_parser.add_argument(
        "--preset",
        default="win10",
        help="Preset identifier to apply. Default: win10",
    )
    enable_parser.add_argument(
        "--no-hide-launchers",
        action="store_true",
        help="Skip hiding Parrot security launchers from the app menu.",
    )
    enable_parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Do not request a plasmashell refresh after switching.",
    )
    enable_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )

    disable_parser = subparsers.add_parser("disable", help="Disable undercover mode.")
    disable_parser.add_argument(
        "--no-restart",
        action="store_true",
        help="Do not request a plasmashell refresh after restoring.",
    )
    disable_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes.",
    )

    subparsers.add_parser("status", help="Show undercover mode status.")
    subparsers.add_parser("doctor", help="Run prerequisite checks.")
    subparsers.add_parser("list-presets", help="List available presets.")
    tools_parser = subparsers.add_parser(
        "tools",
        help="Unlock and launch protected GUI tools.",
    )
    tools_parser.add_argument(
        "--desktop-id",
        help="Launch a specific protected desktop entry after authentication.",
    )
    subparsers.add_parser(
        "reset",
        help="Clear stale lock files without deleting active restore metadata.",
    )
    return parser


def _configure_logging(verbosity: int) -> None:
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(args.verbose)
    manager = UndercoverMode()

    try:
        if args.command == "enable":
            result = manager.enable(
                preset_id=args.preset,
                hide_launchers=not args.no_hide_launchers,
                restart=not args.no_restart,
                dry_run=args.dry_run,
            )
            print_json(result)
            return 0

        if args.command == "disable":
            result = manager.disable(
                restart=not args.no_restart,
                dry_run=args.dry_run,
            )
            print_json(result)
            return 0

        if args.command == "status":
            print_json(manager.status())
            return 0

        if args.command == "doctor":
            result = manager.doctor()
            print_json(result)
            return 0 if result["ready"] else 1

        if args.command == "list-presets":
            print_json({"presets": [preset.to_dict() for preset in manager.list_presets()]})
            return 0

        if args.command == "tools":
            result = manager.tools(desktop_id=args.desktop_id)
            print_json(result)
            return 0

        if args.command == "reset":
            result = manager.reset()
            print_json(result)
            return 0

        parser.error("unknown command")
        return 2
    except UndercoverError as exc:
        if (
            args.command == "tools"
            and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
            and shutil.which("kdialog")
        ):
            subprocess.run(
                ["kdialog", "--title", "Administrative Tools", "--error", str(exc)],
                check=False,
            )
        print_json({"error": str(exc)})
        return 1
