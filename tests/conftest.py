from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from parrot_undercover.core import UndercoverMode

MINIMAL_PRESET = {
    "id": "test",
    "name": "Test Preset",
    "package_id": "org.test.preset",
    "package_name": "Test Preset Package",
    "wallpaper_asset": "wallpaper.svg",
    "start_icon_asset": "start.svg",
    "color_scheme": "TestColors",
    "color_scheme_asset": "test.colors",
    "plasma_theme": "default",
    "icon_theme": "breeze",
    "gtk_theme": "Adwaita",
    "gtk_icon_theme": "breeze",
    "cursor_theme": "breeze_cursors",
    "prefer_dark": False,
    "launcher_desktop_ids": ["org.kde.dolphin.desktop"],
    "hide_filename_globs": ["parrot-*.desktop"],
    "hide_content_markers": [],
    "app_disguises": {
        "org.kde.konsole.desktop": {
            "name": "Test Terminal",
            "icon_asset": "start.svg",
        }
    },
}


@pytest.fixture()
def fake_home(tmp_path: Path) -> Path:
    """Create a fake home directory with the expected subdirectories."""
    config = tmp_path / ".config"
    config.mkdir()
    (config / "kdedefaults").mkdir()
    (config / "gtk-3.0").mkdir()
    (config / "gtk-4.0").mkdir()
    return tmp_path


@pytest.fixture()
def manager(tmp_path: Path, fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> UndercoverMode:
    """Create an UndercoverMode wired to temp directories."""
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    presets_dir = package_root / "presets"
    presets_dir.mkdir()
    assets_dir = package_root / "assets"
    assets_dir.mkdir()
    templates_dir = package_root / "templates" / "look-and-feel" / "contents" / "layouts"
    templates_dir.mkdir(parents=True)
    (package_root / "templates" / "look-and-feel" / "contents" / "defaults").write_text(
        "wallpaper=__WALLPAPER_URI__\n", encoding="utf-8"
    )
    (package_root / "templates" / "look-and-feel" / "metadata.json").write_text(
        json.dumps({"KPlugin": {"Id": "__PACKAGE_ID__"}}), encoding="utf-8"
    )
    (templates_dir / "org.kde.plasma.desktop-layout.js").write_text(
        (
            'var panel = new Panel;\n'
            'panel.location = "bottom";\n'
            'var clock = panel.addWidget("org.kde.plasma.digitalclock");\n'
            'clock.currentConfigGroup = ["Appearance"];\n'
            'clock.writeConfig("use24hFormat", "1");\n'
            'var showDesktop = panel.addWidget("org.kde.plasma.showdesktop");\n'
            'showDesktop.currentConfigGroup = ["General"];\n'
            'showDesktop.writeConfig("icon", "desktop-symbolic");\n'
            'var x = "__START_ICON_PATH__";\n'
        ),
        encoding="utf-8",
    )

    # Create preset
    preset_file = presets_dir / "test.json"
    preset_file.write_text(json.dumps(MINIMAL_PRESET), encoding="utf-8")

    # Create asset stubs
    (assets_dir / "wallpaper.svg").write_text("<svg/>", encoding="utf-8")
    (assets_dir / "start.svg").write_text("<svg/>", encoding="utf-8")
    (assets_dir / "test.colors").write_text("[General]\nColorScheme=TestColors\n", encoding="utf-8")
    for asset_name in (
        "windows-file.svg",
        "windows-folder.svg",
        "windows-folder-open.svg",
        "windows-folder-documents.svg",
        "windows-folder-downloads.svg",
        "windows-folder-pictures.svg",
        "windows-folder-music.svg",
        "windows-folder-videos.svg",
        "windows-folder-desktop.svg",
        "windows-text-file.svg",
    ):
        (assets_dir / asset_name).write_text("<svg/>", encoding="utf-8")

    monkeypatch.setattr(Path, "home", lambda: fake_home)

    mgr = UndercoverMode()
    mgr.package_root = package_root
    mgr.assets_root = assets_dir
    mgr.presets_root = presets_dir
    mgr.template_root = package_root / "templates" / "look-and-feel"
    return mgr


def write_preset(presets_dir: Path, data: dict[str, Any], filename: str = "test.json") -> Path:
    """Helper to write a preset JSON file."""
    path = presets_dir / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path
