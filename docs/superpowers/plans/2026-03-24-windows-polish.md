# Windows Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the undercover desktop indistinguishable from Windows 10 at a glance by fixing the taskbar layout, adding CMD/File Explorer icon disguises, adding CPU/RAM monitors, and fixing the settings apply order.

**Architecture:** Three layers of changes: (1) new SVG icon assets + a preset field `app_disguises` that maps desktop IDs to custom names/icons, (2) a `_apply_app_disguises` method in `core.py` that creates `.desktop` overrides with renamed names/icons during enable and restores on disable, (3) taskbar layout JS updated to match Win10 ordering with search, monitors, and show-desktop. Settings apply order is fixed so `_apply_base_settings` runs after look-and-feel so kwriteconfig6 values aren't clobbered.

**Tech Stack:** Python 3.11+, KDE Plasma layout JS, SVG assets, pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/parrot_undercover/assets/cmd-prompt.svg` | Create | CMD icon SVG (dark terminal with C:\> prompt) |
| `src/parrot_undercover/assets/file-explorer.svg` | Create | Yellow folder icon SVG |
| `src/parrot_undercover/presets/win10.json` | Modify | Add `app_disguises` field |
| `src/parrot_undercover/presets/win10-dark.json` | Modify | Add `app_disguises` field |
| `src/parrot_undercover/core.py` | Modify | Add `app_disguises` to Preset, add `_apply_app_disguises`, fix apply order |
| `src/parrot_undercover/templates/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js` | Modify | Add search, CPU/RAM monitors, show-desktop |
| `tests/conftest.py` | Modify | Update `MINIMAL_PRESET` with `app_disguises` |
| `tests/test_core.py` | Modify | Add tests for app disguises |
| `tests/test_preset.py` | No change | Existing validation tests cover new field via dataclass introspection |

---

### Task 1: Create CMD and File Explorer SVG icons

**Files:**
- Create: `src/parrot_undercover/assets/cmd-prompt.svg`
- Create: `src/parrot_undercover/assets/file-explorer.svg`

- [ ] **Step 1: Create CMD prompt icon**

Create `src/parrot_undercover/assets/cmd-prompt.svg` — a 64x64 icon: dark rounded-rect background with white `C:\>_` text, resembling the real Windows CMD icon.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="4" y="8" width="56" height="48" rx="3" fill="#0c0c0c"/>
  <rect x="4" y="8" width="56" height="14" rx="3" fill="#1e1e1e"/>
  <rect x="4" y="19" width="56" height="37" rx="0" fill="#0c0c0c"/>
  <text x="8" y="18" font-family="Consolas,monospace" font-size="8" fill="#aaa">Command Prompt</text>
  <text x="10" y="38" font-family="Consolas,monospace" font-size="11" font-weight="bold" fill="#cccccc">C:\&gt;_</text>
</svg>
```

- [ ] **Step 2: Create File Explorer icon**

Create `src/parrot_undercover/assets/file-explorer.svg` — a 64x64 yellow folder icon with a blue tab, resembling the Windows File Explorer icon.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M6 18h22l4-6h26a3 3 0 0 1 3 3v35a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V21a3 3 0 0 1 3-3z" fill="#f0c430"/>
  <path d="M6 14h18l4 4H6z" fill="#dca918"/>
  <rect x="3" y="24" width="58" height="29" rx="2" fill="#f5d04e" opacity="0.85"/>
  <path d="M3 24h58v4H3z" fill="#e8b818" opacity="0.5"/>
</svg>
```

- [ ] **Step 3: Verify assets exist**

Run: `ls -la src/parrot_undercover/assets/cmd-prompt.svg src/parrot_undercover/assets/file-explorer.svg`
Expected: Both files present.

---

### Task 2: Add `app_disguises` to presets and Preset dataclass

**Files:**
- Modify: `src/parrot_undercover/presets/win10.json`
- Modify: `src/parrot_undercover/presets/win10-dark.json`
- Modify: `src/parrot_undercover/core.py:26-98` (Preset dataclass and validation)
- Modify: `tests/conftest.py:11-29` (MINIMAL_PRESET)

- [ ] **Step 1: Update test fixture first**

In `tests/conftest.py`, add `app_disguises` to `MINIMAL_PRESET`:

```python
MINIMAL_PRESET = {
    ...existing fields...,
    "app_disguises": {
        "org.kde.konsole.desktop": {
            "name": "Test Terminal",
            "icon_asset": "start.svg"
        }
    },
}
```

- [ ] **Step 2: Add field to Preset dataclass in core.py**

In `src/parrot_undercover/core.py`, add after `hide_content_markers` (line 43):

```python
    app_disguises: dict[str, dict[str, str]]
```

In `from_file` validation, add after the list field checks (after line 96):

```python
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
                    f"Preset '{path.name}': app_disguises['{desktop_id}'] must have 'name' and 'icon_asset'."
                )
```

- [ ] **Step 3: Run tests — expect some failures from stale presets**

Run: `.venv/bin/pytest tests/test_preset.py -v`
Expected: Tests pass (MINIMAL_PRESET updated, dataclass introspection picks up new field).

- [ ] **Step 4: Update real presets**

In `src/parrot_undercover/presets/win10.json`, add before the closing `}`:

```json
  "app_disguises": {
    "org.kde.konsole.desktop": {
      "name": "Command Prompt",
      "icon_asset": "cmd-prompt.svg"
    },
    "org.kde.dolphin.desktop": {
      "name": "File Explorer",
      "icon_asset": "file-explorer.svg"
    }
  }
```

In `src/parrot_undercover/presets/win10-dark.json`, add the identical `app_disguises` block.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass.

---

### Task 3: Implement `_apply_app_disguises` in core.py

**Files:**
- Modify: `src/parrot_undercover/core.py` (new method + wire into enable)
- Modify: `tests/test_core.py` (new test class)

- [ ] **Step 1: Write the test**

Add to `tests/test_core.py`:

```python
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
        # Write a preset with empty disguises
        from tests.conftest import MINIMAL_PRESET, write_preset
        import copy
        empty_preset_data = copy.deepcopy(MINIMAL_PRESET)
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
```

- [ ] **Step 2: Run test — expect fail (method doesn't exist)**

Run: `.venv/bin/pytest tests/test_core.py::TestAppDisguises -v`
Expected: FAIL — `AttributeError: _apply_app_disguises`

- [ ] **Step 3: Implement `_apply_app_disguises`**

In `src/parrot_undercover/core.py`, add new method after `_hide_security_launchers` (after line 648):

```python
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
```

- [ ] **Step 4: Run test — expect pass**

Run: `.venv/bin/pytest tests/test_core.py::TestAppDisguises -v`
Expected: All 3 pass.

- [ ] **Step 5: Wire into enable()**

In `src/parrot_undercover/core.py`, in the `enable()` method, add after the `_hide_security_launchers` block (after line 314):

```python
                log.info("Applying app disguises")
                disguised_apps = self._apply_app_disguises(backup_dir, manifest, preset)
```

Add `"disguised_apps": disguised_apps` to the `state` dict and the return dict.

Also install disguise icon assets in `_install_assets` — add after existing asset copies:

```python
        for disguise in preset.app_disguises.values():
            icon_src = self.assets_root / disguise["icon_asset"]
            icon_dst = target_dir / disguise["icon_asset"]
            if icon_src.exists():
                self._copy_file(icon_src, icon_dst)
```

- [ ] **Step 6: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass.

---

### Task 4: Fix settings apply order

**Files:**
- Modify: `src/parrot_undercover/core.py:290-306` (enable method)

- [ ] **Step 1: Reorder in enable()**

Move `_apply_base_settings` to run AFTER `_apply_look_and_feel` and `_apply_color_scheme`. The new order in `enable()` should be:

1. `_install_assets`
2. `_install_color_scheme`
3. `_install_look_and_feel_package`
4. `_apply_look_and_feel` (applies the layout, may clobber config values)
5. `_apply_base_settings` (re-sets kwriteconfig6 values that look-and-feel may have overwritten)
6. `_apply_color_scheme` (applies color scheme last, highest priority)
7. `_write_gtk_settings`

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass (this is an ordering change, doesn't affect test logic).

---

### Task 5: Update taskbar layout JS

**Files:**
- Modify: `src/parrot_undercover/templates/look-and-feel/contents/layouts/org.kde.plasma.desktop-layout.js`

- [ ] **Step 1: Rewrite layout JS**

The new layout order should be: Start | Search | Pinned apps | spacer | CPU monitor | RAM monitor | tray | clock | show-desktop

```javascript
var panel = new Panel
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.5 / 2);

var launcher = panel.addWidget("org.kde.plasma.kicker");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("useCustomButtonImage", "true");
launcher.writeConfig("customButtonImage", "__START_ICON_PATH__");
launcher.writeConfig("alphaSort", "true");
launcher.writeConfig("limitDepth", "true");
launcher.writeConfig("showIconsRootLevel", "true");
launcher.writeConfig("showRecentApps", "false");
launcher.writeConfig("showRecentDocs", "false");

var search = panel.addWidget("org.kde.milou");

var taskManager = panel.addWidget("org.kde.plasma.icontasks");
taskManager.currentConfigGroup = ["General"];
taskManager.writeConfig("launchers", "__TASK_LAUNCHERS__");
taskManager.writeConfig("fill", "false");
taskManager.writeConfig("iconSpacing", "1");
taskManager.writeConfig("groupPopups", "true");

var spacer = panel.addWidget("org.kde.plasma.panelspacer");
spacer.currentConfigGroup = ["General"];
spacer.writeConfig("expanding", "true");

var cpuMonitor = panel.addWidget("org.kde.plasma.systemmonitor.cpu");
cpuMonitor.currentConfigGroup = ["Appearance"];
cpuMonitor.writeConfig("chartFace", "org.kde.ksysguard.textonly");
cpuMonitor.writeConfig("title", "CPU");

var memMonitor = panel.addWidget("org.kde.plasma.systemmonitor.memory");
memMonitor.currentConfigGroup = ["Appearance"];
memMonitor.writeConfig("chartFace", "org.kde.ksysguard.textonly");
memMonitor.writeConfig("title", "RAM");

var tray = panel.addWidget("org.kde.plasma.systemtray");
tray.currentConfigGroup = ["General"];
tray.writeConfig("iconSpacing", "1");

var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", "true");
clock.writeConfig("dateFormat", "shortDate");
clock.writeConfig("dateDisplayFormat", "2");
clock.writeConfig("showSeconds", "0");
clock.writeConfig("use24hFormat", "1");

panel.addWidget("org.kde.plasma.showdesktop");

var desktopsArray = desktopsForActivity(currentActivity());
for (var j = 0; j < desktopsArray.length; j++) {
    desktopsArray[j].wallpaperPlugin = "org.kde.image";
}
```

- [ ] **Step 2: Run template expansion test**

Run: `.venv/bin/pytest tests/test_core.py::TestTemplateExpansion -v`
Expected: Pass (test only checks placeholder substitution, not widget content).

---

### Task 6: Update pyproject.toml package-data and run final verification

**Files:**
- Modify: `pyproject.toml` (no change needed — `assets/*.svg` already covers new SVGs)

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/pytest tests/ -v`
Expected: All pass.

- [ ] **Step 2: Run doctor**

Run: `parrot-undercover doctor`
Expected: `ready: true`, no missing assets.

- [ ] **Step 3: Verify list-presets shows new field**

Run: `parrot-undercover list-presets`
Expected: Both presets listed with `app_disguises` showing `Command Prompt` and `File Explorer` entries.
