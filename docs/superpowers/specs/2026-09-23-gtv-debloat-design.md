# gtv-debloat — Design Spec

**Date:** 2026-09-23
**Status:** Approved (design), pending spec review
**Author:** emrecan.bilgili

## Purpose

Google TV devices (e.g. Arçelik-branded sets) ship with preinstalled bloatware:
ad/recommendation services, unused vendor apps, and background processes that
consume RAM/network and clutter the home screen with ads. These are flagged as
"system apps" and cannot be removed from the TV's own settings.

`gtv-debloat` is a small PC-side command-line tool that connects to a Google TV
over the network via ADB and lets the user **disable** (not delete) these apps
using `pm disable-user --user 0`. No root required. Nothing is permanently
removed — every change is reversible with a single command, no factory reset.

The tool exists because the raw ADB workflow requires memorizing commands and
knowing which packages are safe to disable versus which will brick the TV. It
automates connection, ships a curated catalog of known-safe bloatware, and
guards critical system packages so a non-expert cannot break their device.

**Audience:** the author plus any Google TV owner frustrated by ads/slowness.
The value is delivered largely through the README (how to enable ADB on Google
TV — most users don't know this) and a community-editable package catalog.

## Non-goals (YAGNI)

- No GUI in v1 (interactive terminal menu only).
- No permanent uninstall (`disable-user` only — reversible by design).
- No on-TV APK component.
- No auto-detection of every possible vendor's bloat — ships one starter
  catalog (Arçelik/Google TV baseline), grown via community PRs.

## Architecture / Flow

Single Python file, no third-party dependencies. Calls the system `adb` binary
via `subprocess`. Logical modules live as functions in the one file:
`adb_utils` (command wrapping), `catalog` (bloat list loading/matching),
`ui` (interactive menu), `main`.

```
1. Check adb is installed        → if not, print install link, exit
2. Connect to device:
   - use USB-attached device if present, OR
   - prompt for TV IP → adb connect IP:5555
3. Fetch packages: adb shell pm list packages -s / -3
4. Match packages against embedded catalog (packages.json):
   - flagged   = known bloat (safe / caution risk level)
   - unflagged = unknown (user takes responsibility)
5. Interactive menu: multi-select by number
6. Confirmation screen → pm disable-user on selected
7. "Undo" menu → re-enable currently disabled packages
```

## Bloatware Catalog + Safety Model

Two-layer safety:

- **Whitelist (never touch):** critical packages — `com.android.*`,
  `com.google.android.gsf`, the launcher, system UI, etc. The tool **never
  displays** these, so they cannot be selected by accident.
- **Known-bloat catalog:** `packages.json` — list of
  `{package, description, risk: safe|caution}`. Disabling an *unknown*
  (uncatalogued) package triggers an extra warning.

`pm disable-user --user 0` is used exclusively — never `uninstall`. Nothing is
permanently deleted; a disabled package returns with a single `enable` command.

The catalog is a separate `packages.json` so the community can extend it via PR
(new devices/packages). The Arçelik Google TV baseline is the starting profile.

## Error Handling

Principle: the tool must never be able to render a TV unbootable.

- `adb` missing → print install instructions + link, exit.
- TV not found / connect fails → show guide: "Is Developer Mode + Network
  debugging enabled on the TV?"
- Connection drops mid-run → clear error, no half-finished batch left silently.
- `pm disable-user` fails (permission / package absent) → skip that package,
  continue with the rest, print a summary at the end ("3 disabled, 1 skipped").
- User attempts to disable a whitelisted package → blocked, reason explained.

## Repo Structure & Testing

```
gtv-debloat/
  gtv_debloat.py       # single-file tool
  packages.json        # bloat catalog (community-edited)
  README.md            # how to enable ADB + usage + GIF
  LICENSE              # MIT
  test_gtv_debloat.py  # tests with mocked adb
```

**Testing:** mock the `adb` calls — with no real TV, verify catalog matching,
whitelist protection, and menu selection logic. Never run a real `pm` command
in tests. Minimum runnable check: a whitelisted package must never appear in
the selectable list (test fails if that protection breaks).

**README** is the most important file for community value: a step-by-step
"how to enable ADB on Google TV" (most owners don't know this), plus usage.

## Milestones

1. Spec (this doc) — approved.
2. Implementation plan (writing-plans skill).
3. v1 build: adb wrapping → catalog → menu → disable/undo → tests → README.
4. Publish to GitHub, invite community PRs to the catalog.
