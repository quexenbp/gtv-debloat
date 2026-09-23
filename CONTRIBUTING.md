# Contributing to gtv-debloat

Thanks for helping other Google TV owners clean up their sets. The most useful
contribution is **expanding the package catalog** with entries for your device.

## Add packages for your TV

1. **List your device's packages.** Connect over ADB (see the README) and run:

   ```bash
   python gtv_debloat.py --serial <IP:PORT>
   ```

   Note the package names shown as `<UNKNOWN>` — those aren't catalogued yet.
   To see the raw list instead: `adb shell pm list packages`.

2. **Classify each package** you want to add, and pick a risk level:

   - `safe` — disabling it won't affect core TV functionality (regional
     streaming apps you don't use, retail/demo apps, factory/test tools).
   - `caution` — may remove a feature you might want (mainstream streaming
     apps, vendor picture/audio/tuner/remote services). When unsure, use
     `caution` — it's the honest, safer label.

   If you can't tell what a package does, **leave it out** rather than guess.
   A wrong `safe` label can lead someone to break their TV.

3. **Add entries to `packages.json`** in this shape:

   ```json
   {"package": "com.example.app", "description": "What it is", "risk": "safe"}
   ```

   Keep descriptions short and factual. Group vendor packages together.

4. **Never add a package that is (or should be) protected.** The whitelist in
   `WHITELIST_PREFIXES` (in `gtv_debloat.py`) covers launcher, permission
   controller, WebView, keyboard, framework overlays, TV Settings, and the
   MediaTek tuner/input services. If you find a critical package on your device
   that is still selectable and would brick the TV when disabled, add its prefix
   to `WHITELIST_PREFIXES` instead of cataloguing it — and mention it in your PR.

## Before you open a PR

Run the tests (they mock ADB, so no device is needed):

```bash
python -m pytest test_gtv_debloat.py -v
```

`test_shipped_catalog_is_valid_and_not_protected` will fail if `packages.json`
is malformed or lists a protected package, and
`test_critical_real_device_packages_are_protected` guards the whitelist.

In your PR description, please include:

- Your TV brand/model and Android TV OS version.
- Which packages you added and how you verified the `safe` ones (e.g. "disabled
  it, TV works normally").

## Reporting a bricking-risk package

If disabling something the tool marked selectable broke a core feature, open an
issue titled `bricking risk: <package>` with your model and what broke. That's a
whitelist bug and takes priority.
