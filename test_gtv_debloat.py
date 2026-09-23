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
