"""Tests for HappyFox API integration (src/it_agent/api.py)."""

import io
import importlib
import pytest
import requests_mock as req_mock_lib


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_api(monkeypatch, endpoint=None, api_key=None, auth_code=None,
                category=None, default_email=None):
    """Set env vars then re-import api so module-level constants are fresh."""
    monkeypatch.setenv("HAPPYFOX_ENDPOINT",
                       endpoint or "https://test.happyfox.com/api/1.1/json/tickets/")
    monkeypatch.setenv("HAPPYFOX_API_KEY", api_key or "test-key")
    monkeypatch.setenv("HAPPYFOX_AUTH_CODE", auth_code or "test-code")
    monkeypatch.setenv("HAPPYFOX_CATEGORY", category or "Helpdesk - Colorado")
    if default_email:
        monkeypatch.setenv("HAPPYFOX_DEFAULT_EMAIL", default_email)

    import src.it_agent.api as api_module
    importlib.reload(api_module)
    # Reset the in-process cache so category fetch always hits the mock
    api_module._category_id_cache = None
    return api_module


CATEGORIES_RESPONSE = [
    {"id": 7, "name": "Helpdesk - Colorado"},
    {"id": 8, "name": "Helpdesk - Other"},
]


# ---------------------------------------------------------------------------
# _build_description
# ---------------------------------------------------------------------------

class TestBuildDescription:
    def test_includes_user_description(self, monkeypatch):
        api = _reload_api(monkeypatch)
        data = {"description": "My printer is broken.", "hostname": "PC-01"}
        result = api._build_description(data)
        assert "My printer is broken." in result

    def test_includes_system_info_block(self, monkeypatch):
        api = _reload_api(monkeypatch)
        data = {
            "description": "Test",
            "hostname": "CLINIC-PC-01",
            "username": "jsmith",
            "local_ip": "192.168.1.5",
            "public_ip": "1.2.3.4",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "os_info": "Windows 11",
            "cpu_usage": 30,
            "ram_usage": 50,
            "total_ram": "16.0 GB",
            "logical_processors": 8,
            "disk_usage": 60,
            "uptime": "2d 3h",
            "battery": "No battery (desktop)",
            "active_window": "Explorer",
        }
        result = api._build_description(data)
        assert "--- System Information ---" in result
        assert "CLINIC-PC-01" in result
        assert "jsmith" in result
        assert "Windows 11" in result
        assert "16.0 GB" in result

    def test_missing_fields_show_na(self, monkeypatch):
        api = _reload_api(monkeypatch)
        result = api._build_description({})
        assert "N/A" in result
        assert "No description provided." in result


# ---------------------------------------------------------------------------
# _get_base_url
# ---------------------------------------------------------------------------

class TestGetBaseUrl:
    def test_strips_tickets_suffix(self, monkeypatch):
        api = _reload_api(monkeypatch,
                          endpoint="https://acme.happyfox.com/api/1.1/json/tickets/")
        assert api._get_base_url() == "https://acme.happyfox.com/api/1.1/json"

    def test_strips_trailing_slash_without_tickets(self, monkeypatch):
        api = _reload_api(monkeypatch,
                          endpoint="https://acme.happyfox.com/api/1.1/json/")
        # Falls through to rsplit logic – last segment removed
        base = api._get_base_url()
        assert base == "https://acme.happyfox.com/api/1.1/json"


# ---------------------------------------------------------------------------
# _fetch_category_id
# ---------------------------------------------------------------------------

class TestFetchCategoryId:
    def test_returns_matching_category_id(self, monkeypatch, requests_mock):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        cat_id = api._fetch_category_id()
        assert cat_id == 7

    def test_caches_result_on_second_call(self, monkeypatch, requests_mock):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        api._fetch_category_id()
        api._fetch_category_id()
        # Only one real HTTP call should have been made
        assert requests_mock.call_count == 1

    def test_falls_back_to_1_on_http_error(self, monkeypatch, requests_mock):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            status_code=500,
        )
        assert api._fetch_category_id() == 1

    def test_falls_back_to_1_on_category_not_found(self, monkeypatch, requests_mock):
        api = _reload_api(monkeypatch, category="Helpdesk - Nonexistent")
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        assert api._fetch_category_id() == 1

    def test_falls_back_to_1_on_connection_error(self, monkeypatch, requests_mock):
        import requests
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            exc=requests.exceptions.ConnectionError,
        )
        assert api._fetch_category_id() == 1


# ---------------------------------------------------------------------------
# send_ticket
# ---------------------------------------------------------------------------

class TestSendTicket:
    def test_success_201_returns_true(self, monkeypatch, requests_mock,
                                     sample_ticket_data):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 42},
        )
        ok, msg = api.send_ticket(sample_ticket_data)
        assert ok is True
        assert "successfully" in msg.lower()

    def test_success_200_also_accepted(self, monkeypatch, requests_mock,
                                      sample_ticket_data):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=200,
            json={"id": 43},
        )
        ok, msg = api.send_ticket(sample_ticket_data)
        assert ok is True

    def test_server_error_returns_false(self, monkeypatch, requests_mock,
                                       sample_ticket_data):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=500,
            text="Internal Server Error",
        )
        ok, msg = api.send_ticket(sample_ticket_data)
        assert ok is False
        assert "500" in msg

    def test_connection_error_returns_false(self, monkeypatch, requests_mock,
                                           sample_ticket_data):
        import requests
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            exc=requests.exceptions.ConnectionError,
        )
        ok, msg = api.send_ticket(sample_ticket_data)
        assert ok is False
        assert "connection" in msg.lower()

    def test_timeout_returns_false(self, monkeypatch, requests_mock,
                                   sample_ticket_data):
        import requests
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            exc=requests.exceptions.Timeout,
        )
        ok, msg = api.send_ticket(sample_ticket_data)
        assert ok is False
        assert "timed out" in msg.lower()

    def test_missing_email_returns_false(self, monkeypatch, requests_mock,
                                        sample_ticket_data):
        api = _reload_api(monkeypatch)
        sample_ticket_data["email"] = ""
        # No HAPPYFOX_DEFAULT_EMAIL set
        monkeypatch.delenv("HAPPYFOX_DEFAULT_EMAIL", raising=False)
        # Categories endpoint should not even be called
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        ok, msg = api.send_ticket(sample_ticket_data)
        assert ok is False
        assert "email" in msg.lower()

    def test_invalid_email_falls_back_to_default(self, monkeypatch, requests_mock,
                                                  sample_ticket_data):
        api = _reload_api(monkeypatch,
                          default_email="fallback@steadmanclinic.com")
        sample_ticket_data["email"] = "not-an-email"
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 99},
        )
        ok, _ = api.send_ticket(sample_ticket_data)
        assert ok is True

    def test_correct_auth_sent(self, monkeypatch, requests_mock, sample_ticket_data):
        api = _reload_api(monkeypatch, api_key="my-key", auth_code="my-code")
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 1},
        )
        api.send_ticket(sample_ticket_data)
        ticket_request = requests_mock.last_request
        assert ticket_request.headers.get("Authorization") is not None

    def test_priority_mapping_high(self, monkeypatch, requests_mock, sample_ticket_data):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 1},
        )
        sample_ticket_data["priority"] = "High"
        api.send_ticket(sample_ticket_data)
        body_text = requests_mock.last_request.text
        # priority=3 for High
        assert "priority=3" in body_text

    def test_priority_mapping_low(self, monkeypatch, requests_mock, sample_ticket_data):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 1},
        )
        sample_ticket_data["priority"] = "Low"
        api.send_ticket(sample_ticket_data)
        body_text = requests_mock.last_request.text
        assert "priority=1" in body_text

    def test_screenshot_attached_when_provided(self, monkeypatch, requests_mock,
                                               sample_ticket_data, png_bytes):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 1},
        )
        api.send_ticket(sample_ticket_data, screenshot_bytes=png_bytes)
        # When files are attached, content-type is multipart
        ct = requests_mock.last_request.headers.get("Content-Type", "")
        assert "multipart" in ct

    def test_no_screenshot_sends_form_data(self, monkeypatch, requests_mock,
                                           sample_ticket_data):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 1},
        )
        api.send_ticket(sample_ticket_data, screenshot_bytes=None)
        ct = requests_mock.last_request.headers.get("Content-Type", "")
        assert "application/x-www-form-urlencoded" in ct

    def test_subject_in_post_body(self, monkeypatch, requests_mock, sample_ticket_data):
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 1},
        )
        sample_ticket_data["subject"] = "Cannot connect to shared drive"
        api.send_ticket(sample_ticket_data)
        body_text = requests_mock.last_request.text
        assert "Cannot+connect+to+shared+drive" in body_text or \
               "Cannot%20connect%20to%20shared%20drive" in body_text or \
               "Cannot connect to shared drive" in body_text

    def test_name_falls_back_to_username_key(self, monkeypatch, requests_mock):
        """When 'name' is absent, fall back to 'username'."""
        api = _reload_api(monkeypatch)
        requests_mock.get(
            "https://test.happyfox.com/api/1.1/json/categories/",
            json=CATEGORIES_RESPONSE,
        )
        requests_mock.post(
            "https://test.happyfox.com/api/1.1/json/tickets/",
            status_code=201,
            json={"id": 1},
        )
        data = {
            "subject": "Test",
            "description": "Test",
            "priority": "Medium",
            "username": "drhouse",
            "email": "drhouse@steadmanclinic.com",
        }
        ok, _ = api.send_ticket(data)
        assert ok is True
