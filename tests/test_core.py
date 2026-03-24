from __future__ import annotations

import json
import os
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path

import pytest

from parrot_undercover.core import UndercoverError, UndercoverMode


class TestListPresets:
    def test_lists_presets(self, manager: UndercoverMode) -> None:
        presets = manager.list_presets()
        assert len(presets) == 1
        assert presets[0].id == "test"

    def test_no_presets_raises(self, manager: UndercoverMode) -> None:
        for f in manager.presets_root.glob("*.json"):
            f.unlink()
        with pytest.raises(UndercoverError, match="No presets"):
            manager.list_presets()


class TestGetPreset:
    def test_found(self, manager: UndercoverMode) -> None:
        preset = manager.get_preset("test")
        assert preset.id == "test"

    def test_not_found(self, manager: UndercoverMode) -> None:
        with pytest.raises(UndercoverError, match="Unknown preset 'nope'"):
            manager.get_preset("nope")

    def test_error_lists_available(self, manager: UndercoverMode) -> None:
        with pytest.raises(UndercoverError, match="Available presets: test"):
            manager.get_preset("nope")


class TestStatus:
    def test_inactive(self, manager: UndercoverMode) -> None:
        result = manager.status()
        assert result == {"active": False}

    def test_active(self, manager: UndercoverMode) -> None:
        manager.state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "active": True,
            "preset": "test",
            "backup_dir": "/tmp/backup",
            "enabled_at": "2025-01-01T00:00:00",
            "hidden_launchers": ["foo.desktop"],
            "disguised_apps": ["org.kde.konsole.desktop"],
            "protected_tools_launcher": "parrot-undercover-tools.desktop",
            "look_and_feel_package": "/tmp/pkg",
        }
        manager.state_file.write_text(json.dumps(state), encoding="utf-8")
        result = manager.status()
        assert result["active"] is True
        assert result["preset"] == "test"
        assert result["hidden_launchers"] == ["foo.desktop"]
        assert result["disguised_apps"] == ["org.kde.konsole.desktop"]
        assert result["protected_tools_launcher"] == "parrot-undercover-tools.desktop"


class TestDoctor:
    def test_reports_structure(self, manager: UndercoverMode) -> None:
        result = manager.doctor()
        assert "commands" in result
        assert "live_apply_commands" in result
        assert "live_apply_ready" in result
        assert "ready" in result
        assert "template_root_exists" in result
        assert "assets_root_exists" in result
        assert "missing_assets" in result
        assert result["template_root_exists"] is True
        assert result["assets_root_exists"] is True
        assert result["missing_assets"] == []
        assert result["missing_gtk_themes"] == []

    def test_missing_assets_detected(self, manager: UndercoverMode) -> None:
        (manager.assets_root / "wallpaper.svg").unlink()
        result = manager.doctor()
        assert len(result["missing_assets"]) == 1
        assert "wallpaper.svg" in result["missing_assets"][0]

    def test_missing_template_dir(self, manager: UndercoverMode) -> None:
        import shutil

        shutil.rmtree(manager.template_root)
        result = manager.doctor()
        assert result["template_root_exists"] is False
        assert result["ready"] is False

    def test_invalid_preset_marks_doctor_not_ready(self, manager: UndercoverMode) -> None:
        preset_file = manager.presets_root / "test.json"
        preset_file.write_text("{bad json\n", encoding="utf-8")

        result = manager.doctor()

        assert result["ready"] is False
        assert result["presets"] == []
        assert "Preset file is not valid JSON" in result["preset_error"]

    def test_missing_gtk_theme_marks_doctor_not_ready(
        self, manager: UndercoverMode, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(manager, "_gtk_theme_exists", lambda _: False)

        result = manager.doctor()

        assert result["ready"] is False
        assert result["missing_gtk_themes"] == ["Adwaita"]


class TestReset:
    def test_clears_lock_and_preserves_state(self, manager: UndercoverMode) -> None:
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text('{"preset": "test"}', encoding="utf-8")
        manager.lock_file.write_text("12345", encoding="utf-8")

        result = manager.reset()
        assert result["reset"] is True
        assert manager.state_file.exists()
        assert not manager.lock_file.exists()
        assert result["removed"] == [str(manager.lock_file)]
        assert result["preserved"] == [str(manager.state_file)]

    def test_nothing_to_clear(self, manager: UndercoverMode) -> None:
        result = manager.reset()
        assert result["reset"] is True
        assert result["removed"] == []
        assert result["preserved"] == []


class TestLock:
    def test_lock_creates_and_cleans(self, manager: UndercoverMode) -> None:
        manager.state_root.mkdir(parents=True, exist_ok=True)
        with manager._lock():
            assert manager.lock_file.exists()
            pid = manager.lock_file.read_text(encoding="utf-8")
            assert pid == str(os.getpid())
        assert not manager.lock_file.exists()

    def test_stale_lock_removed(self, manager: UndercoverMode) -> None:
        manager.state_root.mkdir(parents=True, exist_ok=True)
        # Write a PID that doesn't exist
        manager.lock_file.write_text("999999999", encoding="utf-8")
        with manager._lock():
            assert manager.lock_file.exists()
        assert not manager.lock_file.exists()

    def test_active_lock_raises(self, manager: UndercoverMode) -> None:
        manager.state_root.mkdir(parents=True, exist_ok=True)
        # Write our own PID (which is definitely running)
        manager.lock_file.write_text(str(os.getpid()), encoding="utf-8")
        with pytest.raises(UndercoverError, match="already running"), manager._lock():
            pass


class TestSnapshotAndRollback:
    def test_snapshot_and_restore(self, manager: UndercoverMode, fake_home: Path) -> None:
        # Create a tracked file with known content
        kdeglobals = fake_home / ".config" / "kdeglobals"
        original_content = "[General]\nColorScheme=ParrotDark\n"
        kdeglobals.write_text(original_content, encoding="utf-8")

        backup_dir = manager.backup_root / "test-backup"
        manifest: dict = {"files": {}, "desktop_overrides": {}}

        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.backup_root.mkdir(parents=True, exist_ok=True)
        manager._snapshot_files(backup_dir, manifest)

        # Verify snapshot was created
        assert str(kdeglobals) in manifest["files"]
        assert manifest["files"][str(kdeglobals)]["exists"] is True

        # Modify the file
        kdeglobals.write_text("[General]\nColorScheme=BreezeLight\n", encoding="utf-8")
        assert kdeglobals.read_text() != original_content

        # Rollback
        manager._rollback(manifest)
        assert kdeglobals.read_text() == original_content

    def test_rollback_removes_file_that_didnt_exist(
        self, manager: UndercoverMode, fake_home: Path
    ) -> None:
        target = fake_home / ".config" / "kdeglobals"
        assert not target.exists()

        backup_dir = manager.backup_root / "test-backup"
        manifest: dict = {"files": {}, "desktop_overrides": {}}

        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.backup_root.mkdir(parents=True, exist_ok=True)
        manager._snapshot_files(backup_dir, manifest)

        # Create the file (simulating what enable would do)
        target.write_text("new content", encoding="utf-8")
        assert target.exists()

        # Rollback should remove it
        manager._rollback(manifest)
        assert not target.exists()


class TestDryRun:
    def test_enable_dry_run(self, manager: UndercoverMode) -> None:
        result = manager.enable(preset_id="test", dry_run=True)
        assert result["dry_run"] is True
        assert result["preset"] == "test"
        assert "would_snapshot" in result
        assert not manager.state_file.exists()

    def test_disable_dry_run(self, manager: UndercoverMode) -> None:
        # Set up active state
        manager.state_root.mkdir(parents=True, exist_ok=True)
        state = {
            "preset": "test",
            "backup_dir": "/tmp/fake",
            "manifest_path": "/tmp/fake/manifest.json",
        }
        manager.state_file.write_text(json.dumps(state), encoding="utf-8")

        result = manager.disable(dry_run=True)
        assert result["dry_run"] is True
        # State file should still exist after dry run
        assert manager.state_file.exists()


class TestTemplateExpansion:
    def test_placeholders_replaced(self, manager: UndercoverMode) -> None:
        preset = manager.get_preset("test")

        # Create asset targets
        target_dir = manager.data_root / "assets" / preset.id
        target_dir.mkdir(parents=True)
        wp = target_dir / preset.wallpaper_asset
        si = target_dir / preset.start_icon_asset
        wp.write_text("<svg/>", encoding="utf-8")
        si.write_text("<svg/>", encoding="utf-8")

        asset_paths = {"wallpaper": wp, "start_icon": si}
        package_path = manager._install_look_and_feel_package(preset, asset_paths)

        metadata = json.loads((package_path / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["KPlugin"]["Id"] == "org.test.preset"

        defaults = (package_path / "contents" / "defaults").read_text(encoding="utf-8")
        assert "__WALLPAPER_URI__" not in defaults
        assert "file://" in defaults

        layout_js = (
            package_path / "contents" / "layouts" / "org.kde.plasma.desktop-layout.js"
        ).read_text(encoding="utf-8")
        assert "__START_ICON_PATH__" not in layout_js
        assert 'writeConfig("icon", "desktop-symbolic");' in layout_js
        assert 'clock.writeConfig("use24hFormat", "1");' in layout_js


class TestLiveAppearance:
    def test_skips_without_live_session(
        self, manager: UndercoverMode, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        preset = manager.get_preset("test")
        wallpaper = fake_home / "wallpaper.svg"
        wallpaper.write_text("<svg/>", encoding="utf-8")

        monkeypatch.delenv("DISPLAY", raising=False)
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")

        result = manager._apply_live_appearance(
            preset,
            {"wallpaper": wallpaper, "start_icon": fake_home / "start.svg"},
        )

        assert result["attempted"] is False
        assert "next graphical login" in result["notes"][0]

    def test_refresh_prefers_systemd_restart(
        self, manager: UndercoverMode, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/fake-bus")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")

        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> dict[str, object]:
            calls.append(command)
            return {"command": command, "returncode": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(manager, "_run", fake_run)
        monkeypatch.setattr(
            "parrot_undercover.core.shutil.which",
            lambda command: f"/bin/{command}",
        )

        result = manager._refresh_plasma()

        assert result["requested"] is True
        assert calls == [["systemctl", "--user", "restart", "plasma-plasmashell.service"]]
        assert result["restart_command"] is not None
        assert "systemctl --user restart plasma-plasmashell.service" in result["restart_command"]

    def test_apply_live_layout_uses_qdbus(
        self, manager: UndercoverMode, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/fake-bus")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")

        package_path = fake_home / "laf"
        layout_path = package_path / "contents" / "layouts" / "org.kde.plasma.desktop-layout.js"
        layout_path.parent.mkdir(parents=True)
        layout_path.write_text(
            'var panel = new Panel;\npanel.location = "bottom";\n',
            encoding="utf-8",
        )

        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> dict[str, object]:
            calls.append(command)
            return {"command": command, "returncode": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(manager, "_run", fake_run)
        monkeypatch.setattr("parrot_undercover.core.shutil.which", lambda _: "/bin/qdbus6")

        result = manager._apply_live_layout(package_path)

        assert result["attempted"] is True
        assert result["applied"] is True
        assert calls[0][0] == "qdbus6"
        assert "existingPanels[i].remove()" in calls[0][-1]
        assert 'panel.location = "bottom";' in calls[0][-1]

    def test_prunes_stale_panel_containments(
        self, manager: UndercoverMode, fake_home: Path
    ) -> None:
        appletsrc = fake_home / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"
        appletsrc.write_text(
            """
[Containments][73]
location=3
plugin=org.kde.panel

[Containments][73][Applets][101]
plugin=org.kde.plasma.kicker

[Containments][73][Applets][101][Configuration][General]
customButtonImage=distributor-logo-parrot

[Containments][73][Applets][102]
plugin=org.kde.plasma.systemtray

[Containments][73][Applets][102][Configuration]
SystrayContainmentId=79

[Containments][79]
plugin=org.kde.plasma.private.systemtray

[Containments][137]
location=4
plugin=org.kde.panel

[Containments][137][Applets][138]
plugin=org.kde.plasma.kicker

[Containments][137][Applets][138][Configuration][General]
customButtonImage=/tmp/fake-start.svg

[Containments][137][Applets][139]
plugin=org.kde.plasma.systemtray

[Containments][137][Applets][139][Configuration]
SystrayContainmentId=145

[Containments][145]
plugin=org.kde.plasma.private.systemtray
""".lstrip(),
            encoding="utf-8",
        )

        result = manager._prune_stale_panel_containments(Path("/tmp/fake-start.svg"))

        updated = appletsrc.read_text(encoding="utf-8")
        assert result["removed_panel_ids"] == ["73"]
        assert result["removed_systray_ids"] == ["79"]
        assert "[Containments][73]" not in updated
        assert "[Containments][79]" not in updated
        assert "[Containments][137]" in updated
        assert "[Containments][145]" in updated

    def test_refresh_falls_back_to_qdbus_method(
        self, manager: UndercoverMode, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/fake-bus")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")

        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> dict[str, object]:
            calls.append(command)
            if command[:4] == ["systemctl", "--user", "restart", "plasma-plasmashell.service"]:
                return {
                    "command": command,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "restart failed",
                }
            if command[-1] == "org.kde.PlasmaShell.refreshCurrentShell":
                return {
                    "command": command,
                    "returncode": 1,
                    "stdout": "",
                    "stderr": "UnknownMethod",
                }
            return {"command": command, "returncode": 0, "stdout": "", "stderr": ""}

        monkeypatch.setattr(manager, "_run", fake_run)
        monkeypatch.setattr(
            "parrot_undercover.core.shutil.which",
            lambda command: f"/bin/{command}",
        )

        result = manager._refresh_plasma()

        assert result["requested"] is True
        assert [call[-1] for call in calls] == [
            "plasma-plasmashell.service",
            "org.kde.PlasmaShell.refreshCurrentShell",
            "org.kde.PlasmaShell.reloadConfig",
        ]
        assert result["restart_command"] is not None
        assert "reloadConfig" in result["restart_command"]

    def test_doctor_accepts_systemctl_without_qdbus(
        self, manager: UndercoverMode, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/tmp/fake-bus")
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")

        def fake_which(command: str) -> str | None:
            if command == "qdbus6":
                return None
            return f"/bin/{command}"

        monkeypatch.setattr("parrot_undercover.core.shutil.which", fake_which)

        result = manager.doctor()

        assert result["ready"] is True
        assert result["live_apply_ready"] is False


class TestBaseSettings:
    def test_writes_kdedefaults(self, manager: UndercoverMode, fake_home: Path) -> None:
        preset = manager.get_preset("test")
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> dict[str, object]:
            calls.append(command)
            return {"command": command, "returncode": 0, "stdout": "", "stderr": ""}

        manager._run = fake_run  # type: ignore[method-assign]

        manager._apply_base_settings(preset)

        assert (fake_home / ".config" / "kdedefaults" / "package").read_text(
            encoding="utf-8"
        ) == "org.test.preset\n"
        defaults_kdeglobals = str(fake_home / ".config" / "kdedefaults" / "kdeglobals")
        defaults_plasmarc = str(fake_home / ".config" / "kdedefaults" / "plasmarc")
        user_kdeglobals = str(fake_home / ".config" / "kdeglobals")
        assert any(defaults_kdeglobals in call for call in calls)
        assert any(defaults_plasmarc in call for call in calls)
        assert any(user_kdeglobals in call for call in calls)


class TestFileManagerSettings:
    def test_writes_dolphin_preferences(self, manager: UndercoverMode, fake_home: Path) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_: object) -> dict[str, object]:
            calls.append(command)
            return {"command": command, "returncode": 0, "stdout": "", "stderr": ""}

        manager._run = fake_run  # type: ignore[method-assign]

        manager._apply_file_manager_settings()

        dolphinrc = str(fake_home / ".config" / "dolphinrc")
        assert any(dolphinrc in call for call in calls)
        assert any("--delete" in call and "DoubleClickViewAction" in call for call in calls)
        assert any("ShowFullPath" in call for call in calls)


class TestManagedIconTheme:
    def test_installs_managed_icon_theme(self, manager: UndercoverMode) -> None:
        from tests.conftest import MINIMAL_PRESET, write_preset

        managed_preset = deepcopy(MINIMAL_PRESET)
        managed_preset["id"] = "managed"
        managed_preset["icon_theme"] = "ParrotUndercoverWin10LightIcons"
        managed_preset["gtk_icon_theme"] = "ParrotUndercoverWin10LightIcons"
        write_preset(manager.presets_root, managed_preset, "managed.json")

        preset = manager.get_preset("managed")
        theme_root = manager._install_managed_icon_theme(preset)

        assert theme_root == manager.icons_root / "ParrotUndercoverWin10LightIcons"
        index_theme = (theme_root / "index.theme").read_text(encoding="utf-8")
        assert "[status/16]" in index_theme
        assert "Context=Status" in index_theme
        assert "[actions/22]" in index_theme
        assert (
            theme_root / "places" / "scalable" / "folder.svg"
        ).read_text(encoding="utf-8") == "<svg/>"
        assert (
            theme_root / "mimetypes" / "scalable" / "text-plain.svg"
        ).read_text(encoding="utf-8") == "<svg/>"
        assert (
            theme_root / "actions" / "scalable" / "folder-open-recent.svg"
        ).read_text(encoding="utf-8") == "<svg/>"
        assert (
            theme_root / "places" / "symbolic" / "folder-download-symbolic.svg"
        ).read_text(encoding="utf-8") == "<svg/>"
        audio_icon = theme_root / "status" / "16" / "audio-volume-medium-symbolic.svg"
        media_icon = theme_root / "actions" / "22" / "media-playback-start-symbolic.svg"
        assert audio_icon.exists()
        assert media_icon.exists()


class TestProtectedTools:
    def test_install_protected_tools_launcher(
        self, manager: UndercoverMode
    ) -> None:
        backup_dir = manager.backup_root / "test-backup"
        manifest: dict = {"files": {}, "desktop_overrides": {}}
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.backup_root.mkdir(parents=True, exist_ok=True)

        manager._resolve_cli_entrypoint = lambda: Path("/tmp/parrot-undercover")  # type: ignore[method-assign]

        launcher_id = manager._install_protected_tools_launcher(backup_dir, manifest)

        target = manager.local_applications_dir / launcher_id
        assert launcher_id == "parrot-undercover-tools.desktop"
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "Name=Administrative Tools" in content
        assert "Exec=/tmp/parrot-undercover tools" in content
        assert str(target) in manifest["desktop_overrides"]

    def test_list_protected_tools(self, manager: UndercoverMode) -> None:
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            json.dumps(
                {
                    "active": True,
                    "preset": "test",
                    "backup_dir": "/tmp/backup",
                    "enabled_at": "2025-01-01T00:00:00",
                    "hidden_launchers": ["parrot-burpsuite.desktop"],
                }
            ),
            encoding="utf-8",
        )
        manager.local_applications_dir.mkdir(parents=True, exist_ok=True)
        (manager.local_applications_dir / "parrot-burpsuite.desktop").write_text(
            "[Desktop Entry]\nName=Burp Suite\nIcon=burp\nExec=burpsuite\nNoDisplay=true\n",
            encoding="utf-8",
        )

        entries = manager.list_protected_tools()

        assert entries == [
            {
                "desktop_id": "parrot-burpsuite.desktop",
                "icon": "burp",
                "name": "Burp Suite",
                "path": str(manager.local_applications_dir / "parrot-burpsuite.desktop"),
            }
        ]

    def test_tools_launches_selected_entry(self, manager: UndercoverMode) -> None:
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            json.dumps(
                {
                    "active": True,
                    "preset": "test",
                    "backup_dir": "/tmp/backup",
                    "enabled_at": "2025-01-01T00:00:00",
                    "hidden_launchers": ["parrot-burpsuite.desktop"],
                }
            ),
            encoding="utf-8",
        )
        manager.local_applications_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = manager.local_applications_dir / "parrot-burpsuite.desktop"
        desktop_file.write_text(
            "[Desktop Entry]\nName=Burp Suite\nIcon=burp\nExec=burpsuite\nNoDisplay=true\n",
            encoding="utf-8",
        )

        launched: list[Path] = []
        manager._prompt_secret = lambda **_kwargs: "secret"  # type: ignore[method-assign]
        manager._verify_password = lambda _password: True  # type: ignore[method-assign]
        manager._prompt_tool_selection = (  # type: ignore[method-assign]
            lambda _entries: "parrot-burpsuite.desktop"
        )
        manager._launch_desktop_file = lambda path: launched.append(path)  # type: ignore[method-assign]

        result = manager.tools()

        assert result == {
            "authenticated": True,
            "cancelled": False,
            "desktop_id": "parrot-burpsuite.desktop",
            "launched": "Burp Suite",
        }
        assert launched == [desktop_file]


class TestAppDisguises:
    def test_disguise_creates_override(
        self, manager: UndercoverMode, fake_home: Path
    ) -> None:
        preset = manager.get_preset("test")
        backup_dir = manager.backup_root / "test-backup"
        manifest: dict = {"files": {}, "desktop_overrides": {}}
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.backup_root.mkdir(parents=True, exist_ok=True)

        # Create a system .desktop file to disguise
        system_apps = fake_home / "usr" / "share" / "applications"
        system_apps.mkdir(parents=True)
        system_desktop = system_apps / "org.kde.konsole.desktop"
        system_desktop.write_text(
            "[Desktop Entry]\nName=Konsole\nIcon=utilities-terminal\nExec=konsole\n",
            encoding="utf-8",
        )

        disguised = manager._apply_app_disguises(backup_dir, manifest, preset, system_apps)

        assert "org.kde.konsole.desktop" in disguised
        override = manager.local_applications_dir / "org.kde.konsole.desktop"
        assert override.exists()
        content = override.read_text(encoding="utf-8")
        assert "Name=Test Terminal" in content
        assert "X-Parrot-Undercover-Managed=true" in content

    def test_disguise_backs_up_existing_override(
        self, manager: UndercoverMode, fake_home: Path
    ) -> None:
        preset = manager.get_preset("test")
        backup_dir = manager.backup_root / "test-backup"
        manifest: dict = {"files": {}, "desktop_overrides": {}}
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.backup_root.mkdir(parents=True, exist_ok=True)

        # Pre-existing user override
        manager.local_applications_dir.mkdir(parents=True, exist_ok=True)
        existing = manager.local_applications_dir / "org.kde.konsole.desktop"
        existing.write_text(
            "[Desktop Entry]\nName=My Custom Konsole\nIcon=my-icon\nExec=konsole\n",
            encoding="utf-8",
        )

        # System file
        system_apps = fake_home / "usr" / "share" / "applications"
        system_apps.mkdir(parents=True)
        (system_apps / "org.kde.konsole.desktop").write_text(
            "[Desktop Entry]\nName=Konsole\nIcon=utilities-terminal\nExec=konsole\n",
            encoding="utf-8",
        )

        manager._apply_app_disguises(backup_dir, manifest, preset, system_apps)

        # Backup should exist
        target_key = str(manager.local_applications_dir / "org.kde.konsole.desktop")
        assert target_key in manifest["desktop_overrides"]
        assert manifest["desktop_overrides"][target_key]["exists"] is True

    def test_no_disguises_is_noop(
        self, manager: UndercoverMode, fake_home: Path
    ) -> None:
        from tests.conftest import MINIMAL_PRESET, write_preset

        empty_preset_data = deepcopy(MINIMAL_PRESET)
        empty_preset_data["id"] = "empty"
        empty_preset_data["app_disguises"] = {}
        write_preset(manager.presets_root, empty_preset_data, "empty.json")

        preset = manager.get_preset("empty")
        backup_dir = manager.backup_root / "test-backup"
        manifest: dict = {"files": {}, "desktop_overrides": {}}
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.backup_root.mkdir(parents=True, exist_ok=True)

        system_apps = fake_home / "usr" / "share" / "applications"
        system_apps.mkdir(parents=True)
        result = manager._apply_app_disguises(backup_dir, manifest, preset, system_apps)
        assert result == []


class TestColorSchemes:
    def test_install_color_scheme(self, manager: UndercoverMode) -> None:
        preset = manager.get_preset("test")

        destination = manager._install_color_scheme(preset)

        assert destination == manager.color_schemes_root / "TestColors.colors"
        assert destination.exists()
        assert destination.read_text(encoding="utf-8").startswith("[General]")


class TestEnableIntegration:
    def test_enable_records_disguised_apps(
        self, manager: UndercoverMode, fake_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager.state_root.mkdir(parents=True, exist_ok=True)
        manager.backup_root.mkdir(parents=True, exist_ok=True)

        wallpaper = fake_home / "wallpaper.svg"
        start_icon = fake_home / "start.svg"
        wallpaper.write_text("<svg/>", encoding="utf-8")
        start_icon.write_text("<svg/>", encoding="utf-8")

        monkeypatch.setattr(manager, "_lock", lambda: nullcontext())
        monkeypatch.setattr(manager, "_snapshot_files", lambda *_args: None)
        monkeypatch.setattr(
            manager,
            "_install_assets",
            lambda _preset: {"wallpaper": wallpaper, "start_icon": start_icon},
        )
        monkeypatch.setattr(
            manager,
            "_install_color_scheme",
            lambda _preset: fake_home / "test.colors",
        )
        monkeypatch.setattr(
            manager,
            "_install_look_and_feel_package",
            lambda *_args: fake_home / "laf",
        )
        monkeypatch.setattr(manager, "_apply_base_settings", lambda *_args: None)
        monkeypatch.setattr(
            manager,
            "_apply_live_appearance",
            lambda *_args: {"attempted": False, "applied": [], "notes": []},
        )
        monkeypatch.setattr(manager, "_apply_file_manager_settings", lambda *_args: None)
        monkeypatch.setattr(
            manager,
            "_apply_live_layout",
            lambda *_args: {"attempted": False, "applied": False, "notes": []},
        )
        monkeypatch.setattr(
            manager,
            "_prune_stale_panel_containments",
            lambda *_args: {"removed_panel_ids": [], "removed_systray_ids": [], "notes": []},
        )
        monkeypatch.setattr(manager, "_write_gtk_settings", lambda *_args: None)
        monkeypatch.setattr(manager, "_hide_security_launchers", lambda *_args: [])
        monkeypatch.setattr(
            manager,
            "_apply_app_disguises",
            lambda *_args: ["org.kde.konsole.desktop"],
        )
        monkeypatch.setattr(manager, "_rebuild_desktop_cache", lambda: None)
        monkeypatch.setattr(manager, "_refresh_plasma", lambda: {"requested": False})

        result = manager.enable("test")

        assert result["disguised_apps"] == ["org.kde.konsole.desktop"]
        assert result["live_layout"] == {"attempted": False, "applied": False, "notes": []}
        state = json.loads(manager.state_file.read_text(encoding="utf-8"))
        assert state["disguised_apps"] == ["org.kde.konsole.desktop"]
        assert state["live_layout"] == {"attempted": False, "applied": False, "notes": []}
