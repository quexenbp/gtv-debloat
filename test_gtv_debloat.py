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
