import pytest
from fastapi.testclient import TestClient

import main


def sample_quote(code="000001"):
    return {
        "f57": code,
        "f58": "平安银行",
        "f43": 10.23,
        "f48": 1270902947.86,
        "f116": 198522543165.54,
        "f117": 198519294680.19,
        "f162": 4.75,
        "f167": 0.52,
        "f170": -1.82,
    }


def test_normalize_code_removes_common_exchange_suffixes():
    assert main.normalize_code("600000.SH") == "600000"
    assert main.normalize_code("000001.sz") == "000001"
    assert main.normalize_code(" sh688535 ") == "688535"


def test_build_secid_infers_market_from_code():
    assert main.build_secid("000001") == "0.000001"
    assert main.build_secid("301150") == "0.301150"
    assert main.build_secid("600000") == "1.600000"
    assert main.build_secid("688535") == "1.688535"


def test_quote_returns_503_when_provider_fails(monkeypatch):
    def fail_provider(code):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(main, "fetch_stock_quote", fail_provider)

    response = TestClient(main.app).get("/quote", params={"code": "000001"})

    assert response.status_code == 503
    assert response.json()["detail"] == "行情数据源暂时不可用"


def test_quote_returns_single_stock_from_provider(monkeypatch):
    monkeypatch.setattr(main, "fetch_stock_quote", lambda code: sample_quote(code))

    response = TestClient(main.app).get("/quote", params={"code": "000001.sz"})

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "000001"
    assert data["name"] == "平安银行"
    assert data["price"] == 10.23
    assert data["change_pct"] == -1.82
    assert data["market_cap"] == pytest.approx(1985.2254316554)


def test_quotes_returns_mixed_results(monkeypatch):
    def fake_fetch(code):
        if code == "999999":
            return None
        return sample_quote(code)

    monkeypatch.setattr(main, "fetch_stock_quote", fake_fetch)

    response = TestClient(main.app).get("/quotes", params={"codes": "000001,999999"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["code"] == "000001"
    assert data[1] == {"code": "999999", "error": "未找到"}
