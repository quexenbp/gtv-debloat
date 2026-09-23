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
