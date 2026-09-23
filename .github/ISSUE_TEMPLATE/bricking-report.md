---
name: Bricking risk
about: A selectable package broke a core TV feature when disabled
title: "bricking risk: <package>"
labels: bug, whitelist
---

## Package

- Package name:
- TV brand / model:
- Android TV OS version:

## What broke

Describe what stopped working after disabling it (home screen, remote, live TV,
picture/audio, input, etc.).

## Recovery

- Did `python gtv_debloat.py --undo` bring it back? (yes / no)
- If not, what did you have to do (manual `pm enable`, factory reset)?

> This is a whitelist gap and takes priority — the package should be protected
> so it can never be selected again.
