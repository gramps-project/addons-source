# DarkModePrefs (Gramps 6.0 addon)

Addon for Gramps desktop that adds a **Dark Mode** preferences panel with:

- `Auto` (follow GNOME system dark mode)
- `Dark` (force dark)
- `Light` (force light)
- Optional GTK theme-name switching (Flatpak fallback uses `Adwaita` + dark flag)
- Optional CSS compatibility fixes

## Relation to existing Theme preferences addon

Gramps already ships a `Theme preferences` addon (`ThemesPrefs`) for manual theme/font control.
`DarkModePrefs` is intentionally focused on dark-mode behavior on modern Linux desktops:

- Adds explicit `Auto` mode that follows GNOME `org.gnome.desktop.interface color-scheme`
- Separates dark/light theme selection for forced modes
- Handles Flatpak-specific `GTK_THEME` override cases with explicit guidance

## AI assistance disclosure

This addon was developed with AI assistance and then reviewed/adjusted by the human contributor.
Tool used: `OpenAI Codex (GPT-5)` from provider `OpenAI` (session date: `2026-02-16`).

## Install (local plugin folder)

Quick install:
```bash
./install-local.sh
```

Manual install:

1. Create plugin folder:
```bash
mkdir -p ~/.local/share/gramps/gramps60/plugins/DarkModePrefs
```
2. Copy addon files:
```bash
cp darkmode.gpr.py darkmode_load.py darkmode.py ~/.local/share/gramps/gramps60/plugins/DarkModePrefs/
```
3. Restart Gramps.
4. Open `Edit -> Preferences` and use the `Dark Mode` tab.

## Fedora/GNOME notes

- If `GTK_THEME` is set globally/shell-wide, Gramps may ignore theme changes from addons.
- In Flatpak, `GTK_THEME` is often set via override; unset it with:
  `flatpak override --user --unset-env=GTK_THEME org.gramps_project.Gramps`
- In `Auto` mode, the addon follows `org.gnome.desktop.interface color-scheme`.
- If Gramps is installed as Flatpak, host themes might not be visible in sandbox unless matching runtime theme extensions are installed.
- If `Theme preferences` is also installed, it may conflict because both addons patch the same Preferences class.

## Packaging as `.addon.tgz`

From this folder:
```bash
tar -czf DarkModePrefs.addon.tgz darkmode.gpr.py darkmode_load.py darkmode.py README.md install-local.sh
```

Import this archive via Gramps plugin manager if you prefer archive-based install.

## Disable conflicting Theme preferences addon

Gramps plugin manager supports hide/unhide, but uninstall is usually manual.

1. Find where `Theme preferences` lives:
```bash
find ~/.local/share/gramps/gramps60/plugins -maxdepth 3 -iname '*theme*' -print
```
2. Disable by moving the folder/file out of `plugins` (safe rollback):
```bash
mkdir -p ~/.local/share/gramps/gramps60/plugins-disabled
mv ~/.local/share/gramps/gramps60/plugins/Themes ~/.local/share/gramps/gramps60/plugins-disabled/ 2>/dev/null || true
```
3. Restart Gramps.
