from __future__ import annotations

import fnmatch
import getpass
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("parrot-undercover")

_SECTION_HEADER_RE = re.compile(r"^\[(.+)\]\s*$")
_TOP_CONTAINMENT_RE = re.compile(r"^Containments\]\[(\d+)$")
_CONTAINMENT_SECTION_RE = re.compile(r"^Containments\]\[(\d+)(?:\].*)?$")
_APPLET_SECTION_RE = re.compile(r"^Containments\]\[(\d+)\]\[Applets\]\[(\d+)$")
_APPLET_CONFIG_SECTION_RE = re.compile(
    r"^Containments\]\[(\d+)\]\[Applets\]\[(\d+)\]\[Configuration(?:\]\[General)?$"
)

_MANAGED_ICON_THEME_SPECS: dict[str, dict[str, str]] = {
    "ParrotUndercoverWin10DarkIcons": {
        "inherits": "breeze-dark,hicolor",
        "name": "Parrot Undercover Windows 10 Dark Icons",
    },
    "ParrotUndercoverWin10LightIcons": {
        "inherits": "breeze,hicolor",
        "name": "Parrot Undercover Windows 10 Light Icons",
    },
}

_MANAGED_ICON_THEME_FIXED_SIZES: tuple[str, ...] = ("16", "22", "24")
_MANAGED_ICON_THEME_FIXED_CONTEXTS: frozenset[str] = frozenset({"mimetypes", "places"})

_MANAGED_ICON_THEME_FILES: dict[tuple[str, str], str] = {
    ("actions/scalable", "folder-open-recent.svg"): "windows-folder-open.svg",
    ("actions/scalable", "folder-symbolic.svg"): "windows-folder.svg",
    ("actions/symbolic", "folder-open-recent-symbolic.svg"): "windows-folder-open.svg",
    ("actions/symbolic", "folder-symbolic.svg"): "windows-folder.svg",
    ("mimetypes/scalable", "application-json.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "application-msword-template.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-msword.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-octet-stream.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-pdf.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-vnd.ms-access.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-vnd.ms-excel.addin.macroenabled.12.svg"): "windows-file.svg",
    (
        "mimetypes/scalable",
        "application-vnd.ms-excel.template.macroenabled.12.svg",
    ): "windows-file.svg",
    (
        "mimetypes/scalable",
        "application-vnd.ms-powerpoint.addin.macroenabled.12.svg",
    ): "windows-file.svg",
    (
        "mimetypes/scalable",
        "application-vnd.ms-powerpoint.template.macroenabled.12.svg",
    ): "windows-file.svg",
    ("mimetypes/scalable", "application-x-bzip-compressed-tar.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-bzip.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-compressed-tar.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-deb.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-desktop.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-executable.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-gzip.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-lzma-compressed-tar.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-ms-dos-executable.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-msdownload.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-rar.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-rpm.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-tar.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-x-zerosize.svg"): "windows-file.svg",
    ("mimetypes/scalable", "application-zip.svg"): "windows-file.svg",
    ("mimetypes/scalable", "audio-x-generic.svg"): "windows-file.svg",
    ("mimetypes/scalable", "image-x-generic.svg"): "windows-file.svg",
    ("mimetypes/scalable", "inode-directory.svg"): "windows-folder.svg",
    ("mimetypes/scalable", "inode-symlink.svg"): "windows-file.svg",
    ("mimetypes/scalable", "package-x-generic.svg"): "windows-file.svg",
    ("mimetypes/scalable", "text-css.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-csv.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-html.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-plain.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-rtf.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-xml.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-c++hdr.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-c++src.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-chdr.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-csrc.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-generic.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-markdown.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-python.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "text-x-script.svg"): "windows-text-file.svg",
    ("mimetypes/scalable", "unknown.svg"): "windows-file.svg",
    ("mimetypes/scalable", "video-x-generic.svg"): "windows-file.svg",
    ("mimetypes/scalable", "x-office-document.svg"): "windows-file.svg",
    ("mimetypes/scalable", "x-office-presentation.svg"): "windows-file.svg",
    ("mimetypes/scalable", "x-office-spreadsheet.svg"): "windows-file.svg",
    ("mimetypes/symbolic", "inode-directory-symbolic.svg"): "windows-folder.svg",
    ("places/scalable", "desktop.svg"): "windows-folder-desktop.svg",
    ("places/scalable", "folder-bookmark.svg"): "windows-folder.svg",
    ("places/scalable", "folder-bookmarks.svg"): "windows-folder.svg",
    ("places/scalable", "folder-desktop.svg"): "windows-folder-desktop.svg",
    ("places/scalable", "folder-documents.svg"): "windows-folder-documents.svg",
    ("places/scalable", "folder-download.svg"): "windows-folder-downloads.svg",
    ("places/scalable", "folder-downloads.svg"): "windows-folder-downloads.svg",
    ("places/scalable", "folder-favorites.svg"): "windows-folder.svg",
    ("places/scalable", "folder-home.svg"): "windows-folder.svg",
    ("places/scalable", "folder-images.svg"): "windows-folder-pictures.svg",
    ("places/scalable", "folder-music.svg"): "windows-folder-music.svg",
    ("places/scalable", "folder-network.svg"): "windows-folder.svg",
    ("places/scalable", "folder-open-recent.svg"): "windows-folder-open.svg",
    ("places/scalable", "folder-open.svg"): "windows-folder-open.svg",
    ("places/scalable", "folder-pictures.svg"): "windows-folder-pictures.svg",
    ("places/scalable", "folder-public.svg"): "windows-folder.svg",
    ("places/scalable", "folder-publicshare.svg"): "windows-folder.svg",
    ("places/scalable", "folder-remote.svg"): "windows-folder.svg",
    ("places/scalable", "folder-saved-search.svg"): "windows-folder.svg",
    ("places/scalable", "folder-templates.svg"): "windows-folder.svg",
    ("places/scalable", "folder-videos.svg"): "windows-folder-videos.svg",
    ("places/scalable", "folder.svg"): "windows-folder.svg",
    ("places/scalable", "user-desktop.svg"): "windows-folder-desktop.svg",
    ("places/scalable", "user-home.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-bookmark-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-bookmarks-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-desktop-symbolic.svg"): "windows-folder-desktop.svg",
    ("places/symbolic", "folder-documents-symbolic.svg"): "windows-folder-documents.svg",
    ("places/symbolic", "folder-download-symbolic.svg"): "windows-folder-downloads.svg",
    ("places/symbolic", "folder-downloads-symbolic.svg"): "windows-folder-downloads.svg",
    ("places/symbolic", "folder-favorites-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-home-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-images-symbolic.svg"): "windows-folder-pictures.svg",
    ("places/symbolic", "folder-music-symbolic.svg"): "windows-folder-music.svg",
    ("places/symbolic", "folder-network-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-open-recent-symbolic.svg"): "windows-folder-open.svg",
    ("places/symbolic", "folder-open-symbolic.svg"): "windows-folder-open.svg",
    ("places/symbolic", "folder-pictures-symbolic.svg"): "windows-folder-pictures.svg",
    ("places/symbolic", "folder-public-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-publicshare-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-remote-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-saved-search-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-templates-symbolic.svg"): "windows-folder.svg",
    ("places/symbolic", "folder-videos-symbolic.svg"): "windows-folder-videos.svg",
    ("places/symbolic", "user-desktop-symbolic.svg"): "windows-folder-desktop.svg",
    ("places/symbolic", "user-home-symbolic.svg"): "windows-folder.svg",
}

_MANAGED_ICON_THEME_PASSTHROUGH_FILES: tuple[tuple[str, str], ...] = (
    ("actions/16", "media-playback-pause-symbolic.svg"),
    ("actions/16", "media-playback-pause.svg"),
    ("actions/16", "media-playback-start-symbolic.svg"),
    ("actions/16", "media-playback-start.svg"),
    ("actions/16", "media-playback-stop-symbolic.svg"),
    ("actions/16", "media-playback-stop.svg"),
    ("actions/16", "player-time-symbolic.svg"),
    ("actions/16", "player-time.svg"),
    ("actions/16", "player-volume-muted-symbolic.svg"),
    ("actions/16", "player-volume-muted.svg"),
    ("actions/16", "player-volume-symbolic.svg"),
    ("actions/16", "player-volume.svg"),
    ("actions/22", "media-playback-pause-symbolic.svg"),
    ("actions/22", "media-playback-pause.svg"),
    ("actions/22", "media-playback-start-symbolic.svg"),
    ("actions/22", "media-playback-start.svg"),
    ("actions/22", "media-playback-stop-symbolic.svg"),
    ("actions/22", "media-playback-stop.svg"),
    ("actions/22", "player-time-symbolic.svg"),
    ("actions/22", "player-time.svg"),
    ("actions/22", "player-volume-muted-symbolic.svg"),
    ("actions/22", "player-volume-muted.svg"),
    ("actions/22", "player-volume-symbolic.svg"),
    ("actions/22", "player-volume.svg"),
    ("actions/24", "media-playback-pause-symbolic.svg"),
    ("actions/24", "media-playback-pause.svg"),
    ("actions/24", "media-playback-start-symbolic.svg"),
    ("actions/24", "media-playback-start.svg"),
    ("actions/24", "media-playback-stop-symbolic.svg"),
    ("actions/24", "media-playback-stop.svg"),
    ("actions/24", "player-time-symbolic.svg"),
    ("actions/24", "player-time.svg"),
    ("actions/24", "player-volume-muted-symbolic.svg"),
    ("actions/24", "player-volume-muted.svg"),
    ("actions/24", "player-volume-symbolic.svg"),
    ("actions/24", "player-volume.svg"),
    ("status/16", "audio-off-symbolic.svg"),
    ("status/16", "audio-off.svg"),
    ("status/16", "audio-on-symbolic.svg"),
    ("status/16", "audio-on.svg"),
    ("status/16", "audio-ready-symbolic.svg"),
    ("status/16", "audio-ready.svg"),
    ("status/16", "audio-volume-high-danger-symbolic.svg"),
    ("status/16", "audio-volume-high-danger.svg"),
    ("status/16", "audio-volume-high-symbolic.svg"),
    ("status/16", "audio-volume-high-warning-symbolic.svg"),
    ("status/16", "audio-volume-high-warning.svg"),
    ("status/16", "audio-volume-high.svg"),
    ("status/16", "audio-volume-low-symbolic.svg"),
    ("status/16", "audio-volume-low.svg"),
    ("status/16", "audio-volume-medium-symbolic.svg"),
    ("status/16", "audio-volume-medium.svg"),
    ("status/16", "audio-volume-muted-symbolic.svg"),
    ("status/16", "audio-volume-muted.svg"),
    ("status/16", "media-playback-paused-symbolic.svg"),
    ("status/16", "media-playback-paused.svg"),
    ("status/16", "media-playback-playing-symbolic.svg"),
    ("status/16", "media-playback-playing.svg"),
    ("status/16", "media-playback-stopped-symbolic.svg"),
    ("status/16", "media-playback-stopped.svg"),
    ("status/16", "microphone-sensitivity-high-symbolic.svg"),
    ("status/16", "microphone-sensitivity-low-symbolic.svg"),
    ("status/16", "microphone-sensitivity-medium-symbolic.svg"),
    ("status/16", "microphone-sensitivity-muted-symbolic.svg"),
    ("status/22", "audio-off-symbolic.svg"),
    ("status/22", "audio-off.svg"),
    ("status/22", "audio-on-symbolic.svg"),
    ("status/22", "audio-on.svg"),
    ("status/22", "audio-ready-symbolic.svg"),
    ("status/22", "audio-ready.svg"),
    ("status/22", "audio-volume-high-danger-symbolic.svg"),
    ("status/22", "audio-volume-high-danger.svg"),
    ("status/22", "audio-volume-high-symbolic.svg"),
    ("status/22", "audio-volume-high-warning-symbolic.svg"),
    ("status/22", "audio-volume-high-warning.svg"),
    ("status/22", "audio-volume-high.svg"),
    ("status/22", "audio-volume-low-symbolic.svg"),
    ("status/22", "audio-volume-low.svg"),
    ("status/22", "audio-volume-medium-symbolic.svg"),
    ("status/22", "audio-volume-medium.svg"),
    ("status/22", "audio-volume-muted-symbolic.svg"),
    ("status/22", "audio-volume-muted.svg"),
    ("status/22", "media-playback-paused-symbolic.svg"),
    ("status/22", "media-playback-paused.svg"),
    ("status/22", "media-playback-playing-symbolic.svg"),
    ("status/22", "media-playback-playing.svg"),
    ("status/22", "media-playback-stopped-symbolic.svg"),
    ("status/22", "media-playback-stopped.svg"),
    ("status/22", "microphone-sensitivity-high-symbolic.svg"),
    ("status/22", "microphone-sensitivity-low-symbolic.svg"),
    ("status/22", "microphone-sensitivity-medium-symbolic.svg"),
    ("status/22", "microphone-sensitivity-muted-symbolic.svg"),
    ("status/24", "audio-off-symbolic.svg"),
    ("status/24", "audio-off.svg"),
    ("status/24", "audio-on-symbolic.svg"),
    ("status/24", "audio-on.svg"),
    ("status/24", "audio-ready-symbolic.svg"),
    ("status/24", "audio-ready.svg"),
    ("status/24", "audio-volume-high-danger-symbolic.svg"),
    ("status/24", "audio-volume-high-danger.svg"),
    ("status/24", "audio-volume-high-symbolic.svg"),
    ("status/24", "audio-volume-high-warning-symbolic.svg"),
    ("status/24", "audio-volume-high-warning.svg"),
    ("status/24", "audio-volume-high.svg"),
    ("status/24", "audio-volume-low-symbolic.svg"),
    ("status/24", "audio-volume-low.svg"),
    ("status/24", "audio-volume-medium-symbolic.svg"),
    ("status/24", "audio-volume-medium.svg"),
    ("status/24", "audio-volume-muted-symbolic.svg"),
    ("status/24", "audio-volume-muted.svg"),
    ("status/24", "media-playback-paused-symbolic.svg"),
    ("status/24", "media-playback-paused.svg"),
    ("status/24", "media-playback-playing-symbolic.svg"),
    ("status/24", "media-playback-playing.svg"),
    ("status/24", "media-playback-stopped-symbolic.svg"),
    ("status/24", "media-playback-stopped.svg"),
    ("status/24", "microphone-sensitivity-high-symbolic.svg"),
    ("status/24", "microphone-sensitivity-low-symbolic.svg"),
    ("status/24", "microphone-sensitivity-medium-symbolic.svg"),
    ("status/24", "microphone-sensitivity-muted-symbolic.svg"),
)


class UndercoverError(RuntimeError):
    pass


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    package_id: str
    package_name: str
    wallpaper_asset: str
    start_icon_asset: str
    color_scheme: str
    color_scheme_asset: str
    plasma_theme: str
    icon_theme: str
    gtk_theme: str
    gtk_icon_theme: str
    cursor_theme: str
    prefer_dark: bool
    launcher_desktop_ids: list[str]
    hide_filename_globs: list[str]
    hide_content_markers: list[str]
    app_disguises: dict[str, dict[str, str]]

    @classmethod
    def from_file(cls, path: Path) -> Preset:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UndercoverError(f"Preset file is not valid JSON: {path} ({exc})") from exc

        if not isinstance(raw, dict):
            raise UndercoverError(f"Preset file must contain a JSON object: {path}")

        expected = {f.name for f in fields(cls)}
        missing = expected - raw.keys()
        extra = raw.keys() - expected
        if missing:
            raise UndercoverError(
                f"Preset '{path.name}' is missing required fields: {', '.join(sorted(missing))}"
            )
        if extra:
            raise UndercoverError(
                f"Preset '{path.name}' has unexpected fields: {', '.join(sorted(extra))}"
            )

        for field_name in (
            "id",
            "name",
            "package_id",
            "package_name",
            "wallpaper_asset",
            "start_icon_asset",
            "color_scheme",
            "color_scheme_asset",
            "plasma_theme",
            "icon_theme",
            "gtk_theme",
            "gtk_icon_theme",
            "cursor_theme",
        ):
            if not isinstance(raw.get(field_name), str) or not raw[field_name].strip():
                raise UndercoverError(
                    f"Preset '{path.name}': field '{field_name}' must be a non-empty string."
                )

        if not isinstance(raw.get("prefer_dark"), bool):
            raise UndercoverError(
                f"Preset '{path.name}': field 'prefer_dark' must be a boolean."
            )

        for field_name in ("launcher_desktop_ids", "hide_filename_globs", "hide_content_markers"):
            if not isinstance(raw.get(field_name), list):
                raise UndercoverError(
                    f"Preset '{path.name}': field '{field_name}' must be a list."
                )

        if not isinstance(raw.get("app_disguises"), dict):
            raise UndercoverError(
                f"Preset '{path.name}': field 'app_disguises' must be a dict."
            )
        for desktop_id, disguise in raw["app_disguises"].items():
            if not isinstance(disguise, dict):
                raise UndercoverError(
                    f"Preset '{path.name}': app_disguises['{desktop_id}'] must be a dict."
                )
            if "name" not in disguise or "icon_asset" not in disguise:
                raise UndercoverError(
                    f"Preset '{path.name}': app_disguises['{desktop_id}'] must have "
                    "'name' and 'icon_asset'."
                )

        return cls(**raw)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UndercoverMode:
    APP_ID = "parrot-undercover"
    TOOLS_LAUNCHER_ID = "parrot-undercover-tools.desktop"

    _LOCK_MAX_ATTEMPTS = 3
    _LOCK_RETRY_DELAY = 0.5
    def __init__(self) -> None:
        self.package_root = Path(__file__).resolve().parent
        self.assets_root = self.package_root / "assets"
        self.presets_root = self.package_root / "presets"
        self.template_root = self.package_root / "templates" / "look-and-feel"

        self.home = Path.home()
        self.state_root = self.home / ".local" / "state" / self.APP_ID
        self.data_root = self.home / ".local" / "share" / self.APP_ID
        self.backup_root = self.state_root / "backups"
        self.state_file = self.state_root / "state.json"
        self.lock_file = self.state_root / "lock"
        self.local_applications_dir = self.home / ".local" / "share" / "applications"
        self.color_schemes_root = self.home / ".local" / "share" / "color-schemes"
        self.icons_root = self.home / ".local" / "share" / "icons"
        self.look_and_feel_root = self.home / ".local" / "share" / "plasma" / "look-and-feel"

        self.tracked_files = [
            self.home / ".config" / "kdeglobals",
            self.home / ".config" / "dolphinrc",
            self.home / ".config" / "plasma-org.kde.plasma.desktop-appletsrc",
            self.home / ".config" / "plasmarc",
            self.home / ".config" / "kcminputrc",
            self.home / ".config" / "kwinrc",
            self.home / ".config" / "ksplashrc",
            self.home / ".config" / "gtkrc",
            self.home / ".config" / "gtkrc-2.0",
            self.home / ".config" / "gtk-3.0" / "settings.ini",
            self.home / ".config" / "gtk-4.0" / "settings.ini",
            self.home / ".config" / "Trolltech.conf",
            self.home / ".config" / "kdedefaults" / "package",
            self.home / ".config" / "kdedefaults" / "kdeglobals",
            self.home / ".config" / "kdedefaults" / "plasmarc",
            self.home / ".config" / "kdedefaults" / "kcminputrc",
            self.home / ".config" / "kdedefaults" / "kwinrc",
            self.home / ".config" / "kdedefaults" / "ksplashrc",
        ]

    def list_presets(self) -> list[Preset]:
        presets = [Preset.from_file(path) for path in sorted(self.presets_root.glob("*.json"))]
        if not presets:
            raise UndercoverError("No presets were found in the project.")
        return presets

    def get_preset(self, preset_id: str) -> Preset:
        presets = self.list_presets()
        for preset in presets:
            if preset.id == preset_id:
                return preset
        available = ", ".join(p.id for p in presets)
        raise UndercoverError(f"Unknown preset '{preset_id}'. Available presets: {available}")

    def status(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {"active": False}
        state = self._read_json(self.state_file)
        return {
            "active": True,
            "preset": state["preset"],
            "backup_dir": state["backup_dir"],
            "enabled_at": state["enabled_at"],
            "hidden_launchers": state.get("hidden_launchers", []),
            "disguised_apps": state.get("disguised_apps", []),
            "protected_tools_launcher": state.get("protected_tools_launcher"),
            "look_and_feel_package": state.get("look_and_feel_package"),
        }

    def doctor(self) -> dict[str, Any]:
        required_command_names = [
            "python3",
            "plasma-apply-colorscheme",
            "kwriteconfig6",
            "desktop-file-validate",
            "kbuildsycoca6",
        ]
        live_apply_command_names = [
            "plasma-apply-wallpaperimage",
            "plasma-apply-desktoptheme",
            "plasma-apply-cursortheme",
            "qdbus6",
        ]
        live_refresh_commands = {
            "systemctl": shutil.which("systemctl"),
            "qdbus6": shutil.which("qdbus6"),
        }
        commands = {name: shutil.which(name) for name in required_command_names}
        live_apply_commands = {name: shutil.which(name) for name in live_apply_command_names}
        live_apply_commands.update(live_refresh_commands)

        template_exists = self.template_root.is_dir()
        assets_exist = self.assets_root.is_dir()
        live_session_ready = self._has_live_session()

        missing_assets: list[str] = []
        missing_gtk_themes: list[str] = []
        preset_error: str | None = None
        try:
            presets = self.list_presets()
            preset_ids = [p.id for p in presets]
            if assets_exist:
                for preset in presets:
                    wp = self.assets_root / preset.wallpaper_asset
                    si = self.assets_root / preset.start_icon_asset
                    cs = self.assets_root / preset.color_scheme_asset
                    if not wp.exists():
                        missing_assets.append(str(wp))
                    if not si.exists():
                        missing_assets.append(str(si))
                    if not cs.exists():
                        missing_assets.append(str(cs))
                    if self._managed_icon_theme_spec(preset.icon_theme):
                        for asset_name in self._managed_icon_theme_asset_names():
                            icon_asset = self.assets_root / asset_name
                            if not icon_asset.exists():
                                missing_assets.append(str(icon_asset))
                    if not self._gtk_theme_exists(preset.gtk_theme):
                        missing_gtk_themes.append(preset.gtk_theme)
        except UndercoverError as exc:
            preset_ids = []
            preset_error = str(exc)

        checks: dict[str, Any] = {
            "commands": commands,
            "live_apply_commands": live_apply_commands,
            "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
            "display": os.environ.get("DISPLAY", ""),
            "wayland_display": os.environ.get("WAYLAND_DISPLAY", ""),
            "dbus_session_bus": os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
            "live_session_ready": live_session_ready,
            "missing_gtk_themes": sorted(set(missing_gtk_themes)),
            "template_root": str(self.template_root),
            "template_root_exists": template_exists,
            "assets_root": str(self.assets_root),
            "assets_root_exists": assets_exist,
            "missing_assets": missing_assets,
            "presets": preset_ids,
            "preset_error": preset_error,
            "active_state": self.state_file.exists(),
        }
        ready = (
            all(commands.values())
            and template_exists
            and assets_exist
            and not missing_assets
            and not missing_gtk_themes
            and bool(preset_ids)
            and preset_error is None
        )
        checks["ready"] = ready
        checks["live_apply_ready"] = (
            ready
            and live_session_ready
            and all(live_apply_commands[name] for name in live_apply_command_names)
            and any(live_refresh_commands.values())
        )
        return checks

    def enable(
        self,
        preset_id: str,
        hide_launchers: bool = True,
        restart: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        preset = self.get_preset(preset_id)
        current = self.status()
        if current["active"]:
            if current["preset"] == preset.id:
                return {
                    "active": True,
                    "preset": preset.id,
                    "backup_dir": current["backup_dir"],
                    "hidden_launchers": current.get("hidden_launchers", []),
                    "message": "Preset is already active.",
                }
            raise UndercoverError(
                "Undercover mode is already active with preset "
                f"'{current['preset']}'. Disable it first."
            )

        if dry_run:
            log.info("Dry run: would enable preset '%s'", preset.id)
            return {
                "dry_run": True,
                "preset": preset.id,
                "would_snapshot": [str(f) for f in self.tracked_files],
                "would_hide_launchers": hide_launchers,
                "would_restart": restart,
            }

        self._ensure_dir(self.state_root)
        self._ensure_dir(self.backup_root)

        with self._lock():
            backup_id = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_dir = self.backup_root / backup_id
            manifest: dict[str, Any] = {
                "preset": preset.id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "files": {},
                "desktop_overrides": {},
            }

            log.info("Snapshotting tracked files to %s", backup_dir)
            self._snapshot_files(backup_dir, manifest)
            try:
                log.info("Installing assets for preset '%s'", preset.id)
                asset_paths = self._install_assets(preset)

                log.info("Installing icon theme")
                self._install_managed_icon_theme(preset)
                color_scheme_path = self._install_color_scheme(preset)

                log.info("Installing look-and-feel package")
                package_path = self._install_look_and_feel_package(preset, asset_paths)

                log.info("Applying base Plasma/KDE settings")
                self._apply_base_settings(preset)
                self._apply_file_manager_settings()

                log.info("Applying live Plasma appearance changes")
                live_apply = self._apply_live_appearance(preset, asset_paths)

                log.info("Applying live Plasma panel layout")
                live_layout = self._apply_live_layout(package_path)
                panel_cleanup = self._prune_stale_panel_containments(asset_paths["start_icon"])
                live_layout["notes"].extend(panel_cleanup["notes"])
                if panel_cleanup["removed_panel_ids"]:
                    live_layout["removed_panel_ids"] = panel_cleanup["removed_panel_ids"]
                if panel_cleanup["removed_systray_ids"]:
                    live_layout["removed_systray_ids"] = panel_cleanup["removed_systray_ids"]

                log.info("Writing GTK settings")
                self._write_gtk_settings(preset)

                hidden_launchers: list[str] = []
                disguised_apps: list[str] = []
                protected_tools_launcher: str | None = None
                if hide_launchers:
                    log.info("Hiding security launchers from app menu")
                    hidden_launchers = self._hide_security_launchers(backup_dir, manifest, preset)
                    if hidden_launchers:
                        log.info("Installing protected tools launcher")
                        protected_tools_launcher = self._install_protected_tools_launcher(
                            backup_dir,
                            manifest,
                        )
                if preset.app_disguises:
                    log.info("Applying desktop entry disguises")
                    disguised_apps = self._apply_app_disguises(backup_dir, manifest, preset)
                if hidden_launchers or disguised_apps or protected_tools_launcher:
                    self._rebuild_desktop_cache()

                manifest_path = backup_dir / "manifest.json"
                self._write_json(manifest_path, manifest)

                state = {
                    "active": True,
                    "preset": preset.id,
                    "enabled_at": datetime.now().isoformat(timespec="seconds"),
                    "backup_dir": str(backup_dir),
                    "manifest_path": str(manifest_path),
                    "color_scheme_path": str(color_scheme_path),
                    "look_and_feel_package": str(package_path),
                    "hidden_launchers": hidden_launchers,
                    "disguised_apps": disguised_apps,
                    "protected_tools_launcher": protected_tools_launcher,
                    "live_apply": live_apply,
                    "live_layout": live_layout,
                }
                self._write_json(self.state_file, state)

                refresh = self._refresh_plasma() if restart else {"requested": False}
                return {
                    "active": True,
                    "preset": preset.id,
                    "backup_dir": str(backup_dir),
                    "color_scheme_path": str(color_scheme_path),
                    "look_and_feel_package": str(package_path),
                    "hidden_launchers": hidden_launchers,
                    "disguised_apps": disguised_apps,
                    "protected_tools_launcher": protected_tools_launcher,
                    "live_apply": live_apply,
                    "live_layout": live_layout,
                    "plasma_refresh": refresh,
                }
            except Exception as exc:
                log.error("Enable failed, rolling back: %s", exc)
                self._rollback(manifest)
                raise UndercoverError(
                    f"Enable failed and the previous state was restored. {exc}"
                ) from exc

    def disable(self, restart: bool = True, dry_run: bool = False) -> dict[str, Any]:
        if not self.state_file.exists():
            raise UndercoverError("Undercover mode is not active.")

        if dry_run:
            state = self._read_json(self.state_file)
            log.info("Dry run: would disable and restore from %s", state["backup_dir"])
            return {
                "dry_run": True,
                "would_restore_from": state["backup_dir"],
                "preset": state["preset"],
                "would_restart": restart,
            }

        with self._lock():
            state = self._read_json(self.state_file)
            manifest_path = Path(state["manifest_path"])
            if not manifest_path.exists():
                raise UndercoverError(f"Backup manifest is missing: {manifest_path}")

            manifest = self._read_json(manifest_path)
            log.info("Restoring from backup: %s", state["backup_dir"])
            self._rollback(manifest)
            self.state_file.unlink(missing_ok=True)
            refresh = self._refresh_plasma() if restart else {"requested": False}
            return {
                "active": False,
                "restored_from": state["backup_dir"],
                "preset": state["preset"],
                "plasma_refresh": refresh,
            }

    def tools(self, desktop_id: str | None = None) -> dict[str, Any]:
        entries = self.list_protected_tools()
        password = self._prompt_secret(
            title="Administrative Tools",
            prompt="Enter your password to unlock protected tools",
        )
        if password is None:
            return {
                "authenticated": False,
                "cancelled": True,
                "launched": None,
            }
        if not self._verify_password(password):
            raise UndercoverError("Authentication failed. Protected tools remain locked.")

        selected_id = desktop_id
        if selected_id is None:
            selected_id = self._prompt_tool_selection(entries)
            if selected_id is None:
                return {
                    "authenticated": True,
                    "cancelled": True,
                    "launched": None,
                }

        entry = next((item for item in entries if item["desktop_id"] == selected_id), None)
        if entry is None:
            raise UndercoverError(f"Unknown protected tool '{selected_id}'.")

        self._launch_desktop_file(Path(entry["path"]))
        return {
            "authenticated": True,
            "cancelled": False,
            "desktop_id": entry["desktop_id"],
            "launched": entry["name"],
        }

    def list_protected_tools(self) -> list[dict[str, str]]:
        if not self.state_file.exists():
            raise UndercoverError("Undercover mode is not active.")

        state = self._read_json(self.state_file)
        hidden_launchers = state.get("hidden_launchers", [])
        if not isinstance(hidden_launchers, list) or not hidden_launchers:
            raise UndercoverError("No protected GUI tools are currently hidden.")

        entries: list[dict[str, str]] = []
        for desktop_id in hidden_launchers:
            desktop_file = self.local_applications_dir / desktop_id
            if not desktop_file.exists():
                desktop_file = Path("/usr/share/applications") / desktop_id
            if not desktop_file.exists():
                continue

            content = desktop_file.read_text(encoding="utf-8", errors="ignore")
            name = self._desktop_entry_value(content, "Name") or desktop_id
            icon = self._desktop_entry_value(content, "Icon") or "applications-system"
            entries.append(
                {
                    "desktop_id": desktop_id,
                    "name": name,
                    "icon": icon,
                    "path": str(desktop_file),
                }
            )

        if not entries:
            raise UndercoverError("No protected GUI tools are available to launch.")
        return sorted(entries, key=lambda item: item["name"].lower())

    def _managed_icon_theme_spec(self, theme_name: str) -> dict[str, str] | None:
        return _MANAGED_ICON_THEME_SPECS.get(theme_name)

    def _managed_icon_theme_asset_names(self) -> list[str]:
        return sorted(set(self._managed_icon_theme_files().values()))

    def _managed_icon_theme_files(self) -> dict[tuple[str, str], str]:
        managed = dict(_MANAGED_ICON_THEME_FILES)
        for (relative_dir, filename), asset_name in _MANAGED_ICON_THEME_FILES.items():
            context_key, size_key = relative_dir.split("/", 1)
            if size_key != "scalable" or context_key not in _MANAGED_ICON_THEME_FIXED_CONTEXTS:
                continue
            for size in _MANAGED_ICON_THEME_FIXED_SIZES:
                managed.setdefault((f"{context_key}/{size}", filename), asset_name)
        return managed

    def _managed_icon_theme_source_roots(self, preset: Preset) -> list[Path]:
        spec = self._managed_icon_theme_spec(preset.icon_theme)
        if spec is None:
            return []
        roots: list[Path] = []
        for theme_name in spec["inherits"].split(","):
            candidate = Path("/usr/share/icons") / theme_name.strip()
            if candidate.exists():
                roots.append(candidate)
        return roots

    def _icon_theme_directory_lines(self, directory: str) -> list[str]:
        section_context = {
            "actions": "Actions",
            "mimetypes": "MimeTypes",
            "places": "Places",
            "status": "Status",
        }
        context_key, size_key = directory.split("/", 1)
        if size_key == "scalable":
            size = 64
            min_size = 16
            max_size = 512
            icon_type = "Scalable"
        elif size_key == "symbolic":
            size = 16
            min_size = 16
            max_size = 16
            icon_type = "Scalable"
        else:
            size = int(size_key)
            min_size = size
            max_size = size
            icon_type = "Fixed"

        return [
            f"[{directory}]",
            f"Context={section_context[context_key]}",
            f"Size={size}",
            f"Type={icon_type}",
            f"MinSize={min_size}",
            f"MaxSize={max_size}",
            "",
        ]

    def reset(self) -> dict[str, Any]:
        removed: list[str] = []
        preserved: list[str] = []
        notes: list[str] = []
        if self.lock_file.exists():
            self.lock_file.unlink()
            removed.append(str(self.lock_file))
            log.info("Removed stale lock file: %s", self.lock_file)
        if self.state_file.exists():
            preserved.append(str(self.state_file))
            notes.append(
                "Active restore metadata was preserved. Run 'disable' to restore the original "
                "desktop state."
            )
            log.info("Preserved active state file: %s", self.state_file)
        elif not removed:
            notes.append("Nothing to clear.")
        return {
            "reset": True,
            "removed": removed,
            "preserved": preserved,
            "notes": notes,
        }

    def _snapshot_files(self, backup_dir: Path, manifest: dict[str, Any]) -> None:
        for target in self.tracked_files:
            entry: dict[str, Any] = {"exists": target.exists()}
            if target.exists():
                relative = target.relative_to(self.home)
                backup_path = backup_dir / "files" / relative
                self._copy_file(target, backup_path)
                entry["backup"] = str(backup_path)
                log.debug("Backed up %s -> %s", target, backup_path)
            else:
                log.debug("Skipped (does not exist): %s", target)
            manifest["files"][str(target)] = entry

    def _install_assets(self, preset: Preset) -> dict[str, Path]:
        target_dir = self.data_root / "assets" / preset.id
        self._ensure_dir(target_dir)

        wallpaper_src = self.assets_root / preset.wallpaper_asset
        start_icon_src = self.assets_root / preset.start_icon_asset
        wallpaper_dst = target_dir / preset.wallpaper_asset
        start_icon_dst = target_dir / preset.start_icon_asset

        if not wallpaper_src.exists():
            raise UndercoverError(f"Wallpaper asset not found: {wallpaper_src}")
        if not start_icon_src.exists():
            raise UndercoverError(f"Start icon asset not found: {start_icon_src}")

        self._copy_file(wallpaper_src, wallpaper_dst)
        self._copy_file(start_icon_src, start_icon_dst)

        for disguise in preset.app_disguises.values():
            icon_src = self.assets_root / disguise["icon_asset"]
            icon_dst = target_dir / disguise["icon_asset"]
            if icon_src.exists():
                self._copy_file(icon_src, icon_dst)

        log.debug("Installed assets to %s", target_dir)
        return {"wallpaper": wallpaper_dst, "start_icon": start_icon_dst}

    def _install_color_scheme(self, preset: Preset) -> Path:
        source = self.assets_root / preset.color_scheme_asset
        destination = self.color_schemes_root / f"{preset.color_scheme}.colors"
        if not source.exists():
            raise UndercoverError(f"Color scheme asset not found: {source}")

        self._copy_file(source, destination)
        log.debug("Installed color scheme %s -> %s", source, destination)
        return destination

    def _install_managed_icon_theme(self, preset: Preset) -> Path | None:
        spec = self._managed_icon_theme_spec(preset.icon_theme)
        if spec is None:
            return None

        target_dir = self.icons_root / preset.icon_theme
        managed_icon_files = self._managed_icon_theme_files()
        theme_dirs = sorted(
            {directory for directory, _filename in managed_icon_files}
            | {directory for directory, _filename in _MANAGED_ICON_THEME_PASSTHROUGH_FILES}
        )
        index_theme = "\n".join(
            ["[Icon Theme]", f"Name={spec['name']}", f"Inherits={spec['inherits']}"]
            + [f"Directories={','.join(theme_dirs)}", ""]
            + [line for directory in theme_dirs for line in self._icon_theme_directory_lines(directory)]
        )
        self._write_text(target_dir / "index.theme", index_theme + "\n")

        for (relative_dir, filename), asset_name in managed_icon_files.items():
            source = self.assets_root / asset_name
            if not source.exists():
                raise UndercoverError(f"Icon asset not found: {source}")
            destination = target_dir / relative_dir / filename
            self._copy_file(source, destination)

        for relative_dir, filename in _MANAGED_ICON_THEME_PASSTHROUGH_FILES:
            destination = target_dir / relative_dir / filename
            for root in self._managed_icon_theme_source_roots(preset):
                candidate = root / relative_dir / filename
                if not candidate.exists():
                    continue
                self._copy_file(candidate, destination)
                break

        log.debug("Installed icon theme %s -> %s", preset.icon_theme, target_dir)
        return target_dir

    def _install_look_and_feel_package(self, preset: Preset, asset_paths: dict[str, Path]) -> Path:
        target_dir = self.look_and_feel_root / preset.package_id
        replacements = {
            "__PACKAGE_ID__": preset.package_id,
            "__PACKAGE_NAME__": preset.package_name,
            "__WALLPAPER_URI__": asset_paths["wallpaper"].resolve().as_uri(),
            "__PLASMA_THEME__": preset.plasma_theme,
            "__COLOR_SCHEME__": preset.color_scheme,
            "__ICON_THEME__": preset.icon_theme,
            "__CURSOR_THEME__": preset.cursor_theme,
            "__START_ICON_PATH__": str(asset_paths["start_icon"].resolve()),
            "__TASK_LAUNCHERS__": ",".join(
                f"applications:{item}" for item in preset.launcher_desktop_ids
            ),
        }

        template_files = {
            self.template_root / "metadata.json": target_dir / "metadata.json",
            self.template_root / "contents" / "defaults": target_dir / "contents" / "defaults",
            self.template_root
            / "contents"
            / "layouts"
            / "org.kde.plasma.desktop-layout.js": target_dir
            / "contents"
            / "layouts"
            / "org.kde.plasma.desktop-layout.js",
        }
        for source, destination in template_files.items():
            if not source.exists():
                raise UndercoverError(f"Template file not found: {source}")
            content = source.read_text(encoding="utf-8")
            for placeholder, value in replacements.items():
                content = content.replace(placeholder, value)
            self._write_text(destination, content)
            log.debug("Rendered template %s -> %s", source.name, destination)
        return target_dir

    def _apply_base_settings(self, preset: Preset) -> None:
        config_root = self.home / ".config"
        defaults_root = config_root / "kdedefaults"
        settings_targets = [config_root, defaults_root]
        commands: list[list[str]] = []

        for root in settings_targets:
            commands.extend(
                [
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "kdeglobals"),
                        "--group",
                        "KDE",
                        "--key",
                        "widgetStyle",
                        "Breeze",
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "kdeglobals"),
                        "--group",
                        "KDE",
                        "--key",
                        "SingleClick",
                        "false",
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "kdeglobals"),
                        "--group",
                        "General",
                        "--key",
                        "ColorScheme",
                        preset.color_scheme,
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "kdeglobals"),
                        "--group",
                        "Icons",
                        "--key",
                        "Theme",
                        preset.icon_theme,
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "plasmarc"),
                        "--group",
                        "Theme",
                        "--key",
                        "name",
                        preset.plasma_theme,
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "kcminputrc"),
                        "--group",
                        "Mouse",
                        "--key",
                        "cursorTheme",
                        preset.cursor_theme,
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "kwinrc"),
                        "--group",
                        "org.kde.kdecoration2",
                        "--key",
                        "library",
                        "org.kde.breeze",
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "kwinrc"),
                        "--group",
                        "org.kde.kdecoration2",
                        "--key",
                        "theme",
                        "Breeze",
                    ],
                    [
                        "kwriteconfig6",
                        "--file",
                        str(root / "ksplashrc"),
                        "--group",
                        "KSplash",
                        "--key",
                        "Theme",
                        "org.kde.Breeze",
                    ],
                ]
            )

        commands.insert(
            1,
            [
                "kwriteconfig6",
                "--file",
                str(config_root / "kdeglobals"),
                "--group",
                "KDE",
                "--key",
                "LookAndFeelPackage",
                preset.package_id,
            ],
        )
        self._write_text(defaults_root / "package", f"{preset.package_id}\n")
        for command in commands:
            log.debug("Running: %s", " ".join(command))
            self._run(command)

    def _apply_file_manager_settings(self) -> None:
        dolphinrc = self.home / ".config" / "dolphinrc"
        commands = [
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "General",
                "--key",
                "AutoExpandFolders",
                "false",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "General",
                "--delete",
                "--key",
                "DoubleClickViewAction",
                "",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "General",
                "--key",
                "ShowFullPath",
                "false",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "General",
                "--key",
                "ShowFullPathInTitlebar",
                "false",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "General",
                "--key",
                "RememberOpenedTabs",
                "false",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "General",
                "--key",
                "ShowToolTips",
                "false",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "General",
                "--key",
                "ShowZoomSlider",
                "false",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "KFileDialog Settings",
                "--key",
                "Places Icons Auto-resize",
                "false",
            ],
            [
                "kwriteconfig6",
                "--file",
                str(dolphinrc),
                "--group",
                "KFileDialog Settings",
                "--key",
                "Places Icons Static Size",
                "20",
            ],
        ]
        for command in commands:
            log.debug("Running: %s", " ".join(command))
            self._run(command)

    def _apply_live_appearance(
        self, preset: Preset, asset_paths: dict[str, Path]
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"attempted": False, "applied": [], "notes": []}
        if not self._has_live_session():
            result["notes"].append(
                "No active KDE graphical session was detected. Staged changes will apply "
                "after the next graphical login."
            )
            return result

        commands = [
            (
                "desktop_theme",
                ["plasma-apply-desktoptheme", preset.plasma_theme],
            ),
            (
                "color_scheme",
                ["plasma-apply-colorscheme", preset.color_scheme],
            ),
            (
                "cursor_theme",
                ["plasma-apply-cursortheme", preset.cursor_theme],
            ),
            (
                "wallpaper",
                ["plasma-apply-wallpaperimage", str(asset_paths["wallpaper"])],
            ),
        ]

        result["attempted"] = True
        for label, command in commands:
            if shutil.which(command[0]) is None:
                result["notes"].append(f"{command[0]} was not found; skipped {label}.")
                continue

            command_result = self._run(command, check=False)
            if command_result["returncode"] == 0:
                result["applied"].append(label)
                continue

            stderr = command_result["stderr"] or command_result["stdout"] or "unknown error"
            result["notes"].append(f"{command[0]} failed while applying {label}: {stderr}")
        return result

    def _apply_live_layout(self, package_path: Path) -> dict[str, Any]:
        result: dict[str, Any] = {"attempted": False, "applied": False, "notes": []}
        if not self._has_live_session():
            result["notes"].append(
                "No active KDE graphical session was detected. Staged panel layout will apply "
                "after the next graphical login."
            )
            return result

        if shutil.which("qdbus6") is None:
            result["notes"].append("qdbus6 was not found; skipped live panel layout apply.")
            return result

        layout_path = package_path / "contents" / "layouts" / "org.kde.plasma.desktop-layout.js"
        if not layout_path.exists():
            result["notes"].append(f"Layout script was not found: {layout_path}")
            return result

        layout_script = layout_path.read_text(encoding="utf-8")
        script = (
            "var existingPanels = panels();\n"
            "for (var i = existingPanels.length - 1; i >= 0; --i) {\n"
            "    existingPanels[i].remove();\n"
            "}\n\n"
            f"{layout_script}"
        )

        result["attempted"] = True
        command_result = self._run(
            [
                "qdbus6",
                "org.kde.plasmashell",
                "/PlasmaShell",
                "org.kde.PlasmaShell.evaluateScript",
                script,
            ],
            check=False,
        )
        if command_result["returncode"] == 0:
            result["applied"] = True
            result["notes"].append("Applied live Plasma panel layout via scripting.")
            return result

        stderr = command_result["stderr"] or command_result["stdout"] or "unknown error"
        result["notes"].append(f"qdbus6 failed while applying the live panel layout: {stderr}")
        return result

    def _prune_stale_panel_containments(self, managed_start_icon: Path) -> dict[str, Any]:
        result: dict[str, Any] = {
            "removed_panel_ids": [],
            "removed_systray_ids": [],
            "notes": [],
        }
        appletsrc = self.home / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"
        if not appletsrc.exists():
            result["notes"].append(
                "Plasma applet configuration was not found; skipped panel cleanup."
            )
            return result

        sections = self._parse_ini_sections(appletsrc.read_text(encoding="utf-8"))
        containments: dict[str, dict[str, str]] = {}
        applets: dict[tuple[str, str], dict[str, str]] = {}

        for name, lines in sections:
            if name is None:
                continue

            if match := _TOP_CONTAINMENT_RE.match(name):
                containments[match.group(1)] = self._parse_ini_key_values(lines)
                continue

            if match := _APPLET_SECTION_RE.match(name):
                containment_id, applet_id = match.group(1), match.group(2)
                applets[(containment_id, applet_id)] = self._parse_ini_key_values(lines)
                continue

            if match := _APPLET_CONFIG_SECTION_RE.match(name):
                containment_id, applet_id = match.group(1), match.group(2)
                applets.setdefault((containment_id, applet_id), {}).update(
                    self._parse_ini_key_values(lines)
                )

        managed_panel_candidates: list[str] = []
        managed_start_icon_path = str(managed_start_icon.resolve())
        panel_ids = [
            containment_id
            for containment_id, data in containments.items()
            if data.get("plugin") == "org.kde.panel"
        ]
        for containment_id in panel_ids:
            kicker_icons = [
                data.get("customButtonImage", "")
                for (panel_id, _applet_id), data in applets.items()
                if panel_id == containment_id and data.get("plugin") == "org.kde.plasma.kicker"
            ]
            if managed_start_icon_path in kicker_icons:
                managed_panel_candidates.append(containment_id)

        if not managed_panel_candidates:
            result["notes"].append(
                "No managed Plasma panel was identified in appletsrc; skipped stale panel cleanup."
            )
            return result

        keep_panel_id = max(managed_panel_candidates, key=int)
        keep_systray_ids = {
            data["SystrayContainmentId"]
            for (panel_id, _applet_id), data in applets.items()
            if panel_id == keep_panel_id
            and data.get("plugin") == "org.kde.plasma.systemtray"
            and data.get("SystrayContainmentId")
        }

        removed_panel_ids = sorted((set(panel_ids) - {keep_panel_id}), key=int)
        removed_systray_ids = sorted(
            [
                containment_id
                for containment_id, data in containments.items()
                if data.get("plugin") == "org.kde.plasma.private.systemtray"
                and containment_id not in keep_systray_ids
            ],
            key=int,
        )
        drop_ids = set(removed_panel_ids) | set(removed_systray_ids)
        if not drop_ids:
            result["notes"].append("No stale Plasma panels were found in appletsrc.")
            return result

        kept_lines: list[str] = []
        for name, lines in sections:
            if name is not None:
                match = _CONTAINMENT_SECTION_RE.match(name)
                if match and match.group(1) in drop_ids:
                    continue
            kept_lines.extend(lines)

        self._write_text(appletsrc, "".join(kept_lines))
        result["removed_panel_ids"] = removed_panel_ids
        result["removed_systray_ids"] = removed_systray_ids
        result["notes"].append(
            "Removed stale Plasma panel containments from appletsrc: "
            f"panels={','.join(removed_panel_ids) or 'none'} "
            f"systemtrays={','.join(removed_systray_ids) or 'none'}."
        )
        return result

    def _write_gtk_settings(self, preset: Preset) -> None:
        gtkrc = (
            f'gtk-theme-name="{preset.gtk_theme}"\n'
            f'gtk-icon-theme-name="{preset.gtk_icon_theme}"\n'
            f'gtk-cursor-theme-name="{preset.cursor_theme}"\n'
            'gtk-font-name="Noto Sans 10"\n'
        )
        self._write_text(self.home / ".config" / "gtkrc-2.0", gtkrc)
        self._write_text(self.home / ".config" / "gtkrc", gtkrc)

        settings_ini = (
            "[Settings]\n"
            f"gtk-theme-name={preset.gtk_theme}\n"
            f"gtk-icon-theme-name={preset.gtk_icon_theme}\n"
            f"gtk-cursor-theme-name={preset.cursor_theme}\n"
            "gtk-font-name=Noto Sans 10\n"
            f"gtk-application-prefer-dark-theme={1 if preset.prefer_dark else 0}\n"
        )
        self._write_text(self.home / ".config" / "gtk-3.0" / "settings.ini", settings_ini)
        self._write_text(self.home / ".config" / "gtk-4.0" / "settings.ini", settings_ini)

    def _hide_security_launchers(
        self, backup_dir: Path, manifest: dict[str, Any], preset: Preset
    ) -> list[str]:
        candidates = self._discover_security_launchers(preset)
        self._ensure_dir(self.local_applications_dir)
        hidden: list[str] = []
        for system_file in candidates:
            target = self.local_applications_dir / system_file.name
            source = target if target.exists() else system_file
            base_text = source.read_text(encoding="utf-8", errors="ignore")

            override_entry: dict[str, Any] = {"exists": target.exists()}
            if target.exists():
                backup_path = backup_dir / "desktop-overrides" / target.name
                self._copy_file(target, backup_path)
                override_entry["backup"] = str(backup_path)
            manifest["desktop_overrides"][str(target)] = override_entry

            updated = self._upsert_desktop_entry_key(base_text, "NoDisplay", "true")
            updated = self._upsert_desktop_entry_key(
                updated, "X-Parrot-Undercover-Managed", "true"
            )
            self._write_text(target, updated)
            hidden.append(system_file.name)
            log.debug("Hidden launcher: %s", system_file.name)
        return hidden

    def _install_protected_tools_launcher(
        self,
        backup_dir: Path,
        manifest: dict[str, Any],
    ) -> str:
        target = self.local_applications_dir / self.TOOLS_LAUNCHER_ID
        override_entry: dict[str, Any] = {"exists": target.exists()}
        if target.exists():
            backup_path = backup_dir / "desktop-overrides" / target.name
            self._copy_file(target, backup_path)
            override_entry["backup"] = str(backup_path)
        manifest["desktop_overrides"][str(target)] = override_entry

        command_path = self._resolve_cli_entrypoint()
        content = "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Version=1.0",
                "Name=Administrative Tools",
                "Comment=Unlock protected administrative utilities",
                f"Exec={command_path} tools",
                "Icon=applications-system",
                "Terminal=false",
                "Categories=System;Utility;",
                "Keywords=tools;admin;security;",
                "StartupNotify=true",
                "NoDisplay=false",
                "X-Parrot-Undercover-Managed=true",
            ]
        )
        self._write_text(target, content + "\n")
        return self.TOOLS_LAUNCHER_ID

    def _discover_security_launchers(self, preset: Preset) -> list[Path]:
        applications_dir = Path("/usr/share/applications")
        if not applications_dir.is_dir():
            log.warning("System applications directory not found: %s", applications_dir)
            return []
        matches: list[Path] = []
        for entry in sorted(applications_dir.glob("*.desktop")):
            try:
                if any(
                    fnmatch.fnmatch(entry.name, pattern)
                    for pattern in preset.hide_filename_globs
                ):
                    matches.append(entry)
                    continue
                if preset.hide_content_markers:
                    content = entry.read_text(encoding="utf-8", errors="ignore")
                    if any(marker in content for marker in preset.hide_content_markers):
                        matches.append(entry)
            except PermissionError:
                log.warning("Permission denied reading %s, skipping", entry)
        return matches

    def _apply_app_disguises(
        self,
        backup_dir: Path,
        manifest: dict[str, Any],
        preset: Preset,
        applications_dir: Path | None = None,
    ) -> list[str]:
        if not preset.app_disguises:
            return []
        if applications_dir is None:
            applications_dir = Path("/usr/share/applications")
        self._ensure_dir(self.local_applications_dir)
        disguised: list[str] = []
        for desktop_id, disguise in preset.app_disguises.items():
            system_file = applications_dir / desktop_id
            target = self.local_applications_dir / desktop_id
            source = target if target.exists() else system_file
            if not source.exists():
                log.warning("Desktop file not found for disguise: %s", desktop_id)
                continue
            base_text = source.read_text(encoding="utf-8", errors="ignore")

            override_entry: dict[str, Any] = {"exists": target.exists()}
            if target.exists():
                backup_path = backup_dir / "desktop-overrides" / target.name
                self._copy_file(target, backup_path)
                override_entry["backup"] = str(backup_path)
            manifest["desktop_overrides"][str(target)] = override_entry

            icon_path = self.data_root / "assets" / preset.id / disguise["icon_asset"]
            if not icon_path.exists():
                icon_src = self.assets_root / disguise["icon_asset"]
                if icon_src.exists():
                    self._copy_file(icon_src, icon_path)

            updated = self._upsert_desktop_entry_key(base_text, "Name", disguise["name"])
            updated = self._upsert_desktop_entry_key(updated, "Icon", str(icon_path))
            updated = self._upsert_desktop_entry_key(
                updated, "X-Parrot-Undercover-Managed", "true"
            )
            self._write_text(target, updated)
            disguised.append(desktop_id)
            log.debug("Disguised %s as '%s'", desktop_id, disguise["name"])
        return disguised

    def _resolve_cli_entrypoint(self) -> Path:
        installed = shutil.which("parrot-undercover")
        if installed:
            return Path(installed)

        repo_launcher = self.package_root.parent.parent / "bin" / "parrot-undercover"
        if repo_launcher.exists():
            return repo_launcher

        raise UndercoverError("Could not resolve the parrot-undercover launcher path.")

    def _prompt_secret(self, title: str, prompt: str) -> str | None:
        if self._has_live_session() and shutil.which("kdialog"):
            result = self._run(
                ["kdialog", "--title", title, "--password", prompt],
                check=False,
            )
            if result["returncode"] != 0:
                return None
            stdout = result["stdout"]
            if not isinstance(stdout, str):
                return None
            return stdout

        if sys.stdin.isatty():
            try:
                return getpass.getpass(f"{prompt}: ")
            except EOFError:
                return None

        raise UndercoverError("No interactive password prompt is available.")

    def _verify_password(self, password: str) -> bool:
        if shutil.which("sudo") is None:
            raise UndercoverError("sudo is required to unlock protected tools.")

        completed = subprocess.run(
            ["sudo", "-S", "-k", "-p", "", "-v"],
            input=password + "\n",
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            log.debug("Protected tools authentication failed: %s", completed.stderr.strip())
            return False

        subprocess.run(
            ["sudo", "-k"],
            capture_output=True,
            text=True,
            check=False,
        )
        return True

    def _prompt_tool_selection(self, entries: list[dict[str, str]]) -> str | None:
        if self._has_live_session() and shutil.which("kdialog"):
            command = [
                "kdialog",
                "--title",
                "Administrative Tools",
                "--menu",
                "Select a protected tool to launch",
            ]
            for entry in entries:
                command.extend([entry["desktop_id"], entry["name"]])
            result = self._run(command, check=False)
            if result["returncode"] != 0:
                return None
            return result["stdout"] or None

        if not sys.stdin.isatty():
            raise UndercoverError("No interactive tool selection prompt is available.")

        for index, entry in enumerate(entries, start=1):
            print(f"{index}. {entry['name']} ({entry['desktop_id']})")
        choice = input("Select a protected tool number (blank to cancel): ").strip()
        if not choice:
            return None
        if not choice.isdigit():
            raise UndercoverError("Invalid tool selection.")
        selected_index = int(choice) - 1
        if selected_index < 0 or selected_index >= len(entries):
            raise UndercoverError("Invalid tool selection.")
        return entries[selected_index]["desktop_id"]

    def _launch_desktop_file(self, desktop_file: Path) -> None:
        if shutil.which("gio") is None:
            raise UndercoverError("gio is required to launch protected tools.")

        try:
            subprocess.Popen(
                ["gio", "launch", str(desktop_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise UndercoverError(f"Could not launch {desktop_file.name}: {exc}") from exc

    def _rebuild_desktop_cache(self) -> None:
        if shutil.which("kbuildsycoca6"):
            log.debug("Rebuilding desktop cache with kbuildsycoca6")
            self._run(["kbuildsycoca6"], check=False)

    def _rollback(self, manifest: dict[str, Any]) -> None:
        for target_str, metadata in manifest["files"].items():
            target = Path(target_str)
            if metadata["exists"]:
                backup_path = Path(metadata["backup"])
                if not backup_path.exists():
                    raise UndercoverError(f"Missing backup for {target}")
                self._copy_file(backup_path, target)
                log.debug("Restored %s from backup", target)
            elif target.exists():
                target.unlink()
                log.debug("Removed %s (did not exist before)", target)

        for target_str, metadata in manifest["desktop_overrides"].items():
            target = Path(target_str)
            if metadata["exists"]:
                backup_path = Path(metadata["backup"])
                if not backup_path.exists():
                    raise UndercoverError(f"Missing backup for launcher override {target}")
                self._copy_file(backup_path, target)
                log.debug("Restored launcher override %s from backup", target)
            elif target.exists():
                target.unlink()
                log.debug("Removed launcher override %s (did not exist before)", target)

        self._rebuild_desktop_cache()

    def _refresh_plasma(self) -> dict[str, Any]:
        result: dict[str, Any] = {"requested": True, "restart_command": None, "notes": []}
        if not self._has_live_session():
            result["requested"] = False
            result["notes"].append(
                "No active KDE graphical session was detected. Log out and back in to "
                "apply staged Plasma changes."
            )
            return result

        failures: list[str] = []

        if shutil.which("systemctl"):
            command = ["systemctl", "--user", "restart", "plasma-plasmashell.service"]
            command_result = self._run(command, check=False)
            if command_result["returncode"] == 0:
                result["restart_command"] = "systemctl --user restart plasma-plasmashell.service"
                result["notes"].append(
                    "Requested a plasma-plasmashell.service restart via systemd."
                )
                return result

            stderr = command_result["stderr"] or command_result["stdout"] or "unknown error"
            failures.append(f"systemctl restart: {stderr}")

        if shutil.which("qdbus6"):
            methods = [
                (
                    "org.kde.PlasmaShell.refreshCurrentShell",
                    "qdbus6 org.kde.plasmashell /PlasmaShell "
                    "org.kde.PlasmaShell.refreshCurrentShell",
                ),
                (
                    "org.kde.PlasmaShell.reloadConfig",
                    "qdbus6 org.kde.plasmashell /PlasmaShell "
                    "org.kde.PlasmaShell.reloadConfig",
                ),
            ]

            for method_name, command_text in methods:
                command_result = self._run(
                    [
                        "qdbus6",
                        "org.kde.plasmashell",
                        "/PlasmaShell",
                        method_name,
                    ],
                    check=False,
                )
                if command_result["returncode"] == 0:
                    result["restart_command"] = command_text
                    result["notes"].append(
                        f"Requested a live plasmashell refresh via {method_name}."
                    )
                    return result

                stderr = command_result["stderr"] or command_result["stdout"] or "unknown error"
                failures.append(f"{method_name}: {stderr}")

        else:
            failures.append("qdbus6: command not found")

        if not failures:
            failures.append("No supported Plasma refresh command was found.")

        result["requested"] = False
        result["notes"].append(
            "Could not signal plasmashell to refresh its configuration. "
            f"Log out and back in to apply staged Plasma changes. ({'; '.join(failures)})"
        )
        return result

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self._ensure_dir(self.state_root)
        for attempt in range(1, self._LOCK_MAX_ATTEMPTS + 1):
            try:
                fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("utf-8"))
                os.close(fd)
                break
            except FileExistsError as exc:
                stale_pid = self.lock_file.read_text(encoding="utf-8", errors="ignore").strip()
                if stale_pid.isdigit() and Path(f"/proc/{stale_pid}").exists():
                    raise UndercoverError(
                        "Another parrot-undercover process is already running."
                    ) from None
                if attempt == self._LOCK_MAX_ATTEMPTS:
                    raise UndercoverError(
                        "Another parrot-undercover process is already running."
                    ) from exc
                log.debug(
                    "Removing stale lock file (attempt %d/%d)",
                    attempt,
                    self._LOCK_MAX_ATTEMPTS,
                )
                self.lock_file.unlink(missing_ok=True)
                time.sleep(self._LOCK_RETRY_DELAY)
        else:
            raise UndercoverError("Failed to acquire lock.")

        try:
            yield
        finally:
            self.lock_file.unlink(missing_ok=True)

    def _run(
        self,
        command: list[str],
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> dict[str, Any]:
        log.debug("$ %s", " ".join(command))
        completed = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
        )
        result = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
        if completed.returncode != 0:
            log.debug("Command exited %d: %s", completed.returncode, result["stderr"])
        if check and completed.returncode != 0:
            raise UndercoverError(
                f"Command failed: {' '.join(command)}\n"
                f"stdout: {result['stdout']}\n"
                f"stderr: {result['stderr']}"
            )
        return result

    def _upsert_desktop_entry_key(self, content: str, key: str, value: str) -> str:
        lines = content.splitlines()
        in_desktop_entry = False
        inserted = False
        updated_lines: list[str] = []

        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("["):
                if in_desktop_entry and not inserted:
                    updated_lines.append(f"{key}={value}")
                    inserted = True
                in_desktop_entry = stripped == "[Desktop Entry]"
                updated_lines.append(line)
                continue

            if in_desktop_entry and line.startswith(f"{key}="):
                updated_lines.append(f"{key}={value}")
                inserted = True
                continue

            updated_lines.append(line)

            if in_desktop_entry and index == len(lines) - 1 and not inserted:
                updated_lines.append(f"{key}={value}")
                inserted = True

        if not inserted:
            if updated_lines and updated_lines[-1] != "":
                updated_lines.append("")
            updated_lines.extend(["[Desktop Entry]", f"{key}={value}"])
        return "\n".join(updated_lines) + "\n"

    def _desktop_entry_value(self, content: str, key: str) -> str | None:
        in_desktop_entry = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_desktop_entry = stripped == "[Desktop Entry]"
                continue
            if in_desktop_entry and stripped.startswith(f"{key}="):
                return stripped.partition("=")[2]
        return None

    def _copy_file(self, source: Path, destination: Path) -> None:
        self._ensure_dir(destination.parent)
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temp_path = Path(handle.name)
        shutil.copy2(source, temp_path)
        temp_path.replace(destination)

    def _parse_ini_sections(self, content: str) -> list[tuple[str | None, list[str]]]:
        sections: list[tuple[str | None, list[str]]] = []
        current_name: str | None = None
        current_lines: list[str] = []

        for line in content.splitlines(keepends=True):
            match = _SECTION_HEADER_RE.match(line.strip())
            if match:
                sections.append((current_name, current_lines))
                current_name = match.group(1)
                current_lines = [line]
                continue
            current_lines.append(line)

        sections.append((current_name, current_lines))
        return sections

    def _parse_ini_key_values(self, lines: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            values[key] = value
        return values

    def _write_text(self, path: Path, content: str) -> None:
        self._ensure_dir(path.parent)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, delete=False, mode="w", encoding="utf-8"
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        temp_path.replace(path)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        self._write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")

    def _read_json(self, path: Path) -> dict[str, Any]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise UndercoverError(f"Expected a JSON object in {path}")
        return data

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def _gtk_theme_exists(self, theme_name: str) -> bool:
        roots = [
            self.home / ".local" / "share" / "themes",
            Path("/usr/local/share/themes"),
            Path("/usr/share/themes"),
        ]
        return any((root / theme_name).exists() for root in roots)

    def _has_live_session(self) -> bool:
        has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        has_bus = bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
        is_kde = os.environ.get("XDG_CURRENT_DESKTOP", "").upper().startswith("KDE")
        return has_display and has_bus and is_kde
