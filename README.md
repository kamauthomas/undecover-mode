# Parrot Undercover

`parrot-undercover` is a Plasma-native undercover mode for Parrot OS. It is built around a snapshot-and-restore workflow so switching back out restores the user configuration that existed before undercover mode was enabled.

## What It Does

- Applies a Windows-style Plasma preset.
- Installs a matching custom color scheme for more Windows-like light and dark accents.
- Installs a generated look-and-feel package in the user profile.
- Hides Parrot security launchers from menus with user-local `.desktop` overrides.
- Adds an `Administrative Tools` launcher that asks for your password before showing hidden GUI tools.
- Leaves command-line access to the underlying tools untouched.
- Restores tracked Plasma and GTK configuration files on disable.

## Current Preset

- `win10`
- `win10-dark`

## Usage

One-time user install so the command works from any terminal:

```bash
./scripts/install-user.sh
```

Then run it from anywhere:

```bash
parrot-undercover doctor
parrot-undercover enable
parrot-undercover status
parrot-undercover tools
parrot-undercover disable
```

Optional flags:

```bash
parrot-undercover enable --preset win10 --no-restart
parrot-undercover enable --preset win10-dark
parrot-undercover enable --no-hide-launchers
parrot-undercover enable --dry-run
parrot-undercover tools --desktop-id parrot-burpsuite.desktop
parrot-undercover disable --no-restart
parrot-undercover disable --dry-run
```

Verbose output for troubleshooting:

```bash
parrot-undercover -v enable      # info-level logging
parrot-undercover -vv enable     # debug-level logging
```

Recovery:

```bash
parrot-undercover reset          # clear stale lock files, preserve restore state
```

## Development

```bash
pip install -e ".[dev]"
pytest
mypy src/
ruff check src/ tests/
```

## Notes

- This version targets KDE Plasma on Parrot OS.
- The first implementation favors safe restore over preserving changes made while undercover mode is active.
- Live appearance updates are applied on a best-effort basis; the tool prefers restarting `plasma-plasmashell.service` through systemd instead of manually killing and replacing `plasmashell`.
- KDE exposes more future polish points through Appearance, Splash Screen, and Screen Locking, but the current implementation keeps changes in the user session layer so restore stays predictable.
- If Plasma does not redraw immediately after a switch, logging out and back in will still pick up the saved configuration.
- The protected GUI tools menu uses your local `sudo` password only for authentication and then launches the selected desktop entry as your normal user session.
