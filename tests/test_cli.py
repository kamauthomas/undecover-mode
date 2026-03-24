from __future__ import annotations

import pytest

from parrot_undercover.cli import build_parser


class TestBuildParser:
    def test_enable_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["enable"])
        assert args.command == "enable"
        assert args.preset == "win10"
        assert args.no_hide_launchers is False
        assert args.no_restart is False
        assert args.dry_run is False

    def test_enable_all_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "enable", "--preset", "macOS", "--no-hide-launchers", "--no-restart", "--dry-run"
        ])
        assert args.preset == "macOS"
        assert args.no_hide_launchers is True
        assert args.no_restart is True
        assert args.dry_run is True

    def test_disable_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["disable"])
        assert args.command == "disable"
        assert args.no_restart is False
        assert args.dry_run is False

    def test_disable_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["disable", "--no-restart", "--dry-run"])
        assert args.no_restart is True
        assert args.dry_run is True

    def test_status(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    def test_doctor(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["doctor"])
        assert args.command == "doctor"

    def test_list_presets(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list-presets"])
        assert args.command == "list-presets"

    def test_tools(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["tools"])
        assert args.command == "tools"
        assert args.desktop_id is None

    def test_tools_with_desktop_id(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["tools", "--desktop-id", "parrot-burpsuite.desktop"])
        assert args.command == "tools"
        assert args.desktop_id == "parrot-burpsuite.desktop"

    def test_reset(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["reset"])
        assert args.command == "reset"

    def test_verbose_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["-v", "status"])
        assert args.verbose == 1

    def test_double_verbose(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["-vv", "status"])
        assert args.verbose == 2

    def test_no_command_raises(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])
