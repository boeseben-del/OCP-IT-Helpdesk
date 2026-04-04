"""Shared pytest fixtures for OCP IT Helpdesk tests."""

import io
import os
import sys
import pytest

# Make the project root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_sysinfo():
    """A realistic sysinfo dict matching what gather_all() returns."""
    return {
        "hostname": "CLINIC-PC-01",
        "local_ip": "192.168.1.100",
        "public_ip": "203.0.113.5",
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "username": "jsmith",
        "user_email": "jsmith@steadmanclinic.com",
        "cpu_usage": 42.5,
        "ram_usage": 61.0,
        "disk_usage": 55.2,
        "os_info": "Windows 11",
        "active_window": "Microsoft Outlook",
        "uptime": "3d 4h 12m",
        "battery": "No battery (desktop)",
        "total_ram": "16.0 GB",
        "logical_processors": 8,
    }


@pytest.fixture
def sample_ticket_data(sample_sysinfo):
    """Ticket data dict as assembled by the GUI before calling send_ticket()."""
    return {
        "subject": "Cannot connect to shared drive",
        "description": "Since the update I can no longer map the Z: drive.",
        "priority": "High",
        "name": sample_sysinfo["username"],
        "email": sample_sysinfo["user_email"],
        **sample_sysinfo,
    }


@pytest.fixture
def png_bytes():
    """Minimal valid PNG as a BytesIO buffer (1x1 white pixel)."""
    # PNG magic bytes + IHDR + IDAT + IEND for a 1x1 white image
    raw = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # magic
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR length + type
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # 8-bit RGB
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT length + type
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,  # compressed data
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xA7, 0x35, 0x81,
        0x84, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND
        0x44, 0xAE, 0x42, 0x60, 0x82,
    ])
    buf = io.BytesIO(raw)
    buf.seek(0)
    return buf


@pytest.fixture
def happyfox_env(monkeypatch):
    """Set HappyFox environment variables for tests."""
    monkeypatch.setenv("HAPPYFOX_ENDPOINT", "https://test.happyfox.com/api/1.1/json/tickets/")
    monkeypatch.setenv("HAPPYFOX_API_KEY", "test-api-key")
    monkeypatch.setenv("HAPPYFOX_AUTH_CODE", "test-auth-code")
    monkeypatch.setenv("HAPPYFOX_CATEGORY", "Helpdesk - Colorado")
    monkeypatch.setenv("HAPPYFOX_DEFAULT_EMAIL", "fallback@steadmanclinic.com")
