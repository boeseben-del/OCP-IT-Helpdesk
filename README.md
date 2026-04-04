# IT Support Agent
Windows Desktop Agent for IT support tickets

## Testing

Install test dependencies and run the suite:

```bash
pip install pytest pytest-cov pytest-mock requests-mock
pytest
```

Or install everything in one shot using the dev extras:

```bash
pip install -e ".[dev]"
pytest
```

Tests cover:
- **HappyFox API** (`tests/test_api.py`) — ticket submission, category lookup, auth, priority mapping, screenshot attachment, error handling
- **Screenshot utilities** (`tests/test_screenshot.py`) — thumbnail resizing, BytesIO buffer contract, fallback behaviour
- **System info** (`tests/test_sysinfo.py`) — all `get_*` helpers and `gather_all()`, with network/psutil calls mocked
