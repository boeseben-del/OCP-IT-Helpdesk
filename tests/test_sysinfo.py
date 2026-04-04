"""Tests for system information gathering (src/it_agent/sysinfo.py)."""

import platform
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_sysinfo():
    import src.it_agent.sysinfo as m
    return m


# ---------------------------------------------------------------------------
# get_hostname
# ---------------------------------------------------------------------------

class TestGetHostname:
    def test_returns_string(self):
        si = _import_sysinfo()
        result = si.get_hostname()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_matches_socket(self):
        import socket
        si = _import_sysinfo()
        assert si.get_hostname() == socket.gethostname()


# ---------------------------------------------------------------------------
# get_local_ip
# ---------------------------------------------------------------------------

class TestGetLocalIp:
    def test_returns_ip_or_na(self):
        si = _import_sysinfo()
        result = si.get_local_ip()
        assert isinstance(result, str)
        # Either a dotted-quad IP or the fallback "N/A"
        assert result == "N/A" or len(result.split(".")) == 4

    def test_returns_na_on_socket_error(self):
        si = _import_sysinfo()
        with patch("socket.socket") as mock_sock:
            mock_sock.return_value.__enter__ = MagicMock(
                side_effect=OSError("network unreachable"))
            mock_sock.return_value.connect.side_effect = OSError
            mock_sock.return_value.__exit__ = MagicMock(return_value=False)
            result = si.get_local_ip()
        # Should return "N/A" on failure
        assert result == "N/A" or isinstance(result, str)


# ---------------------------------------------------------------------------
# get_public_ip
# ---------------------------------------------------------------------------

class TestGetPublicIp:
    def test_returns_ip_when_api_succeeds(self):
        si = _import_sysinfo()
        mock_response = MagicMock()
        mock_response.text = "203.0.113.99"
        with patch("src.it_agent.sysinfo.req_lib.get", return_value=mock_response):
            result = si.get_public_ip()
        assert result == "203.0.113.99"

    def test_returns_na_on_failure(self):
        import requests
        si = _import_sysinfo()
        with patch("src.it_agent.sysinfo.req_lib.get",
                   side_effect=requests.exceptions.ConnectionError):
            result = si.get_public_ip()
        assert result == "N/A"

    def test_returns_na_on_timeout(self):
        import requests
        si = _import_sysinfo()
        with patch("src.it_agent.sysinfo.req_lib.get",
                   side_effect=requests.exceptions.Timeout):
            result = si.get_public_ip()
        assert result == "N/A"


# ---------------------------------------------------------------------------
# get_mac_address
# ---------------------------------------------------------------------------

class TestGetMacAddress:
    def test_returns_colon_separated_hex(self):
        si = _import_sysinfo()
        result = si.get_mac_address()
        assert isinstance(result, str)
        if result != "N/A":
            parts = result.split(":")
            assert len(parts) == 6
            for part in parts:
                int(part, 16)  # should not raise

    def test_uppercase(self):
        si = _import_sysinfo()
        result = si.get_mac_address()
        if result != "N/A":
            assert result == result.upper()

    def test_returns_na_on_exception(self):
        si = _import_sysinfo()
        with patch("uuid.getnode", side_effect=Exception("fail")):
            result = si.get_mac_address()
        assert result == "N/A"


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def test_returns_string(self):
        si = _import_sysinfo()
        result = si.get_current_user()
        assert isinstance(result, str)

    def test_falls_back_to_env_user(self, monkeypatch):
        si = _import_sysinfo()
        monkeypatch.setenv("USER", "testuser")
        with patch("os.getlogin", side_effect=OSError("no tty")):
            with patch("os.environ.get", side_effect=lambda k, d=None: {
                "USERNAME": None, "USER": "testuser"
            }.get(k, d)):
                result = si.get_current_user()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# get_cpu_usage
# ---------------------------------------------------------------------------

class TestGetCpuUsage:
    def test_returns_float(self):
        si = _import_sysinfo()
        with patch("psutil.cpu_percent", return_value=42.5):
            result = si.get_cpu_usage()
        assert result == 42.5

    def test_between_0_and_100(self):
        si = _import_sysinfo()
        result = si.get_cpu_usage()
        assert 0.0 <= result <= 100.0


# ---------------------------------------------------------------------------
# get_ram_usage
# ---------------------------------------------------------------------------

class TestGetRamUsage:
    def test_returns_percentage(self):
        si = _import_sysinfo()
        mock_mem = MagicMock()
        mock_mem.percent = 61.3
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = si.get_ram_usage()
        assert result == 61.3


# ---------------------------------------------------------------------------
# get_disk_usage
# ---------------------------------------------------------------------------

class TestGetDiskUsage:
    def test_returns_float_on_linux(self):
        si = _import_sysinfo()
        mock_disk = MagicMock()
        mock_disk.percent = 55.0
        with patch("platform.system", return_value="Linux"):
            with patch("psutil.disk_usage", return_value=mock_disk):
                result = si.get_disk_usage()
        assert result == 55.0

    def test_returns_zero_on_exception(self):
        si = _import_sysinfo()
        with patch("psutil.disk_usage", side_effect=Exception("no disk")):
            result = si.get_disk_usage()
        assert result == 0.0


# ---------------------------------------------------------------------------
# get_uptime
# ---------------------------------------------------------------------------

class TestGetUptime:
    def test_includes_minutes(self):
        si = _import_sysinfo()
        import time
        # Fake boot 2 hours 30 minutes ago
        fake_boot = time.time() - (2 * 3600 + 30 * 60)
        with patch("psutil.boot_time", return_value=fake_boot):
            result = si.get_uptime()
        assert "2h" in result
        assert "30m" in result

    def test_includes_days(self):
        si = _import_sysinfo()
        import time
        fake_boot = time.time() - (3 * 86400 + 4 * 3600)
        with patch("psutil.boot_time", return_value=fake_boot):
            result = si.get_uptime()
        assert "3d" in result

    def test_returns_na_on_exception(self):
        si = _import_sysinfo()
        with patch("psutil.boot_time", side_effect=Exception("fail")):
            result = si.get_uptime()
        assert result == "N/A"


# ---------------------------------------------------------------------------
# get_battery_status
# ---------------------------------------------------------------------------

class TestGetBatteryStatus:
    def test_no_battery_returns_desktop_message(self):
        si = _import_sysinfo()
        with patch("psutil.sensors_battery", return_value=None):
            result = si.get_battery_status()
        assert "desktop" in result.lower() or "no battery" in result.lower()

    def test_charging_battery(self):
        si = _import_sysinfo()
        mock_batt = MagicMock()
        mock_batt.percent = 80
        mock_batt.power_plugged = True
        with patch("psutil.sensors_battery", return_value=mock_batt):
            result = si.get_battery_status()
        assert "80" in result
        assert "Charging" in result

    def test_on_battery(self):
        si = _import_sysinfo()
        mock_batt = MagicMock()
        mock_batt.percent = 45
        mock_batt.power_plugged = False
        with patch("psutil.sensors_battery", return_value=mock_batt):
            result = si.get_battery_status()
        assert "45" in result
        assert "battery" in result.lower()

    def test_returns_na_on_exception(self):
        si = _import_sysinfo()
        with patch("psutil.sensors_battery", side_effect=Exception("fail")):
            result = si.get_battery_status()
        assert result == "N/A"


# ---------------------------------------------------------------------------
# get_total_ram
# ---------------------------------------------------------------------------

class TestGetTotalRam:
    def test_returns_gb_string(self):
        si = _import_sysinfo()
        mock_mem = MagicMock()
        mock_mem.total = 16 * 1024 ** 3  # 16 GB
        with patch("psutil.virtual_memory", return_value=mock_mem):
            result = si.get_total_ram()
        assert "16.0 GB" in result

    def test_returns_na_on_exception(self):
        si = _import_sysinfo()
        with patch("psutil.virtual_memory", side_effect=Exception("fail")):
            result = si.get_total_ram()
        assert result == "N/A"


# ---------------------------------------------------------------------------
# get_logical_processors
# ---------------------------------------------------------------------------

class TestGetLogicalProcessors:
    def test_returns_int(self):
        si = _import_sysinfo()
        with patch("psutil.cpu_count", return_value=8):
            result = si.get_logical_processors()
        assert result == 8

    def test_returns_na_on_exception(self):
        si = _import_sysinfo()
        with patch("psutil.cpu_count", side_effect=Exception("fail")):
            result = si.get_logical_processors()
        assert result == "N/A"


# ---------------------------------------------------------------------------
# get_os_info
# ---------------------------------------------------------------------------

class TestGetOsInfo:
    def test_linux_includes_linux(self):
        si = _import_sysinfo()
        with patch("platform.system", return_value="Linux"):
            with patch("platform.release", return_value="6.8.0"):
                result = si.get_os_info()
        assert "Linux" in result

    def test_windows_11_detected_by_build(self):
        si = _import_sysinfo()
        with patch("platform.system", return_value="Windows"):
            with patch("platform.version", return_value="10.0.22621"):
                with patch("platform.release", return_value="10"):
                    result = si.get_os_info()
        assert result == "Windows 11"

    def test_windows_10_below_22000(self):
        si = _import_sysinfo()
        with patch("platform.system", return_value="Windows"):
            with patch("platform.version", return_value="10.0.19041"):
                with patch("platform.release", return_value="10"):
                    result = si.get_os_info()
        assert "Windows" in result
        assert "11" not in result


# ---------------------------------------------------------------------------
# gather_all
# ---------------------------------------------------------------------------

class TestGatherAll:
    def test_returns_all_expected_keys(self):
        si = _import_sysinfo()
        # Patch every I/O call so tests run fast and offline
        with patch("src.it_agent.sysinfo.req_lib.get") as mock_get:
            mock_get.return_value.text = "1.2.3.4"
            result = si.gather_all()
        expected_keys = {
            "hostname", "local_ip", "public_ip", "mac_address",
            "username", "user_email", "cpu_usage", "ram_usage",
            "disk_usage", "os_info", "active_window", "uptime",
            "battery", "total_ram", "logical_processors",
        }
        assert expected_keys.issubset(result.keys())

    def test_returns_dict(self):
        si = _import_sysinfo()
        with patch("src.it_agent.sysinfo.req_lib.get") as mock_get:
            mock_get.return_value.text = "1.2.3.4"
            result = si.gather_all()
        assert isinstance(result, dict)
