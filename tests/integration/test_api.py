import pytest
from fastapi.testclient import TestClient

from src.timefm_trader import config
from src.timefm_trader.models import BotState, TradeMode
from src.timefm_trader.web import app

TOKEN = "test-token"


@pytest.fixture(autouse=True)
def setup_app(monkeypatch):
    monkeypatch.setattr(config, "CONTROL_API_TOKEN", TOKEN)
    mock_state = BotState(
        mode=TradeMode.PAPER,
        running=True,
        paused=False,
        balance_usd=10000,
        initial_balance=10000,
        positions={},
        trade_history=[],
        active_insights=[],
        total_fees_paid=0,
        coins_scanned=0,
        last_scan_time=None,
        signals_found=0,
    )
    app.state.state_provider = lambda: mock_state
    commands_received = []

    async def mock_handler(cmd):
        commands_received.append(cmd)
        return {"ok": True}

    app.state.command_handler = mock_handler
    app.state.command_log = []
    return commands_received


@pytest.fixture
def client():
    return TestClient(app)


def auth_headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_get_control_state_returns_200(client):
    r = client.get("/control/state", headers=auth_headers())
    assert r.status_code == 200


def test_get_control_state_returns_401_without_token(client):
    r = client.get("/control/state")
    assert r.status_code == 401


def test_get_control_state_returns_401_with_wrong_token(client):
    r = client.get("/control/state", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_post_control_trading_pause(client, setup_app):
    r = client.post("/control/trading", json={"action": "pause"}, headers=auth_headers())
    assert r.status_code == 200
    assert setup_app[-1]["type"] == "trading"
    assert setup_app[-1]["action"] == "pause"


def test_post_control_risk(client):
    r = client.post("/control/risk", json={"stop_loss_pct": -0.06}, headers=auth_headers())
    assert r.status_code == 200


def test_post_control_insight(client):
    body = {
        "coin": "BTCUSDT",
        "direction": "bearish",
        "strength": 0.8,
        "reason": "test",
        "ttl_minutes": 60,
    }
    r = client.post("/control/insight", json=body, headers=auth_headers())
    assert r.status_code == 200


def test_post_control_position_force_sell(client):
    r = client.post(
        "/control/position",
        json={"action": "force_sell", "coin": "BTCUSDT"},
        headers=auth_headers(),
    )
    assert r.status_code == 200


def test_websocket_delivers_json(client):
    with client.websocket_connect("/ws") as ws:
        data = ws.receive_json()
        assert "balance_usd" in data or isinstance(data, dict)
