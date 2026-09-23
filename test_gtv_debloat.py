from unittest.mock import patch
import gtv_debloat as g

def test_list_packages_parses_and_sorts():
    fake = (0, "package:com.b\npackage:com.a\npackage:com.a\n", "")
    with patch.object(g, "run_adb", return_value=fake):
        assert g.list_packages() == ["com.a", "com.b"]

def test_list_packages_forwards_flag_and_serial():
    with patch.object(g, "run_adb", return_value=(0, "", "")) as m:
        g.list_packages(serial="1.2.3.4:5555", flag="-s")
        m.assert_called_once_with(["shell", "pm", "list", "packages", "-s"],
                                  serial="1.2.3.4:5555")

def test_protected_packages_never_selectable():
    installed = ["com.android.systemui", "com.google.android.gsf",
                 "com.arcelik.bloat", "com.random.app"]
    catalog = {"com.arcelik.bloat": {"description": "demo", "risk": "safe"}}
    result = g.selectable_packages(installed, catalog)
    names = [p.package for p in result]
    assert "com.android.systemui" not in names
    assert "com.google.android.gsf" not in names
    assert "com.arcelik.bloat" in names

def test_classify_known_vs_unknown():
    installed = ["com.arcelik.bloat", "com.random.app"]
    catalog = {"com.arcelik.bloat": {"description": "demo", "risk": "safe"}}
    by_name = {p.package: p for p in g.selectable_packages(installed, catalog)}
    assert by_name["com.arcelik.bloat"].risk == "safe"
    assert by_name["com.arcelik.bloat"].description == "demo"
    assert by_name["com.random.app"].risk == "unknown"

def test_load_catalog_reads_json(tmp_path):
    f = tmp_path / "packages.json"
    f.write_text('{"packages":[{"package":"com.x","description":"d","risk":"caution"}]}')
    cat = g.load_catalog(f)
    assert cat["com.x"] == {"description": "d", "risk": "caution"}

def test_disable_refuses_protected_and_reports_summary():
    calls = []
    def fake_run(args, serial=None):
        calls.append(args)
        return (0, "", "")
    with patch.object(g, "run_adb", side_effect=fake_run):
        res = g.disable_packages(["com.arcelik.bloat", "com.android.systemui"])
    assert res["disabled"] == ["com.arcelik.bloat"]
    assert res["skipped"] == ["com.android.systemui"]
    # protected package must not have hit adb
    assert all("com.android.systemui" not in a for a in calls)

def test_disable_marks_failed_as_skipped():
    def fake_run(args, serial=None):
        return (1, "", "Failure")
    with patch.object(g, "run_adb", side_effect=fake_run):
        res = g.disable_packages(["com.x"])
    assert res["disabled"] == []
    assert res["skipped"] == ["com.x"]

def test_parse_selection_handles_commas_spaces_and_bounds():
    assert g.parse_selection("1 3 3 5", 4) == [1, 3]      # 5 out of range dropped
    assert g.parse_selection("0,2", 3) == [0, 2]
    assert g.parse_selection("x 1 -2", 3) == [1]          # garbage/negative dropped
    assert g.parse_selection("", 3) == []

def test_ensure_connected_returns_serial_on_success():
    with patch.object(g, "run_adb", return_value=(0, "connected to 1.2.3.4:5555", "")):
        assert g.ensure_connected("1.2.3.4") == "1.2.3.4:5555"

def test_ensure_connected_returns_none_on_failure():
    with patch.object(g, "run_adb", return_value=(1, "", "cannot connect")):
        assert g.ensure_connected("1.2.3.4") is None

def test_main_unknown_pkg_aborts_without_yes(tmp_path):
    cat = tmp_path / "packages.json"
    cat.write_text('{"packages": []}')  # nothing catalogued -> selected pkg is "unknown"
    inputs = iter(["0", "no"])  # select index 0, then decline the yes-gate
    with patch.object(g, "adb_available", return_value=True), \
         patch.object(g, "ensure_connected", return_value=None), \
         patch.object(g, "list_packages", return_value=["com.some.app"]), \
         patch.object(g, "disable_packages") as mock_disable, \
         patch("builtins.input", lambda _="": next(inputs)):
        rc = g.main(["--catalog", str(cat)])
    assert rc == 0
    mock_disable.assert_not_called()  # aborted, nothing disabled

def test_main_unknown_pkg_proceeds_with_yes(tmp_path):
    cat = tmp_path / "packages.json"
    cat.write_text('{"packages": []}')
    inputs = iter(["0", "yes"])
    with patch.object(g, "adb_available", return_value=True), \
         patch.object(g, "ensure_connected", return_value=None), \
         patch.object(g, "list_packages", return_value=["com.some.app"]), \
         patch.object(g, "disable_packages", return_value={"disabled": ["com.some.app"], "skipped": []}) as mock_disable, \
         patch("builtins.input", lambda _="": next(inputs)):
        rc = g.main(["--catalog", str(cat)])
    assert rc == 0
    mock_disable.assert_called_once()  # confirmed -> disable happened


def test_critical_real_device_packages_are_protected():
    # Regression guard from real Arcelik/MediaTek Google TV testing:
    # disabling any of these can brick or make the TV unusable, so they must
    # never appear as selectable (and thus never be disable-able).
    critical = [
        "com.google.android.apps.tv.launcherx",       # home launcher
        "com.google.android.permissioncontroller",
        "com.google.android.overlay.googlewebview",   # any framework RRO overlay
        "com.google.android.modulemetadata",
        "com.google.android.inputmethod.latin",       # only keyboard
        "com.google.android.webview",
        "com.google.android.ext.services",
        "com.mediatek.tv.service",
        "com.mediatek.tv.service.rro",
        "com.mediatek.tvinput",
    ]
    sel = g.selectable_packages(critical, {})
    assert sel == [], f"critical packages leaked into selectable: {[p.package for p in sel]}"


def test_shipped_catalog_is_valid_and_not_protected():
    # The real packages.json must load and must not list any package that the
    # whitelist protects (a protected package in the catalog is dead weight and
    # a sign the two lists disagree).
    catalog = g.load_catalog("packages.json")
    assert catalog, "catalog is empty"
    leaked = [p for p in catalog if g.is_protected(p)]
    assert leaked == [], f"catalog lists protected packages: {leaked}"
