import time
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

EASTMONEY_STOCK_URLS = (
    "https://push2.eastmoney.com/api/qt/stock/get",
    "https://82.push2.eastmoney.com/api/qt/stock/get",
    "https://push2delay.eastmoney.com/api/qt/stock/get",
)
EASTMONEY_STOCK_FIELDS = "f43,f48,f57,f58,f116,f117,f162,f167,f170"
CACHE_TTL_SECONDS = 15

app = FastAPI(
    title="Stock GPT API",
    description="A股实时行情、估值查询接口，用于 ChatGPT Actions",
    version="1.0.0",
    servers=[
        {
            "url": "https://stock-gpt-api-hz4w.onrender.com",
            "description": "Render production server"
        }
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_quote_cache: dict[str, dict[str, Any]] = {}


def normalize_code(code: str) -> str:
    value = code.strip().lower()
    for prefix in ("sh", "sz", "bj"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    for suffix in (".sh", ".sz", ".bj", "sh", "sz", "bj"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
    return value.strip()


def safe_float(value: Any, scale: float = 1.0) -> float | None:
    if value in (None, "-", ""):
        return None
    try:
        return float(value) / scale
    except (TypeError, ValueError):
        return None


def build_secid(code: str) -> str:
    stock_code = normalize_code(code)
    if stock_code.startswith(("5", "6", "9")):
        market = "1"
    else:
        market = "0"
    return f"{market}.{stock_code}"


def fetch_stock_quote(code: str) -> dict[str, Any] | None:
    stock_code = normalize_code(code)
    now = time.monotonic()
    cached = _quote_cache.get(stock_code)
    if cached is not None and now < cached["expires_at"]:
        return cached["data"]

    params = {
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fltt": 2,
        "invt": 2,
        "secid": build_secid(stock_code),
        "fields": EASTMONEY_STOCK_FIELDS,
    }
    last_error = None
    for url in EASTMONEY_STOCK_URLS:
        session = requests.Session()
        session.trust_env = False
        try:
            response = session.get(url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            break
        except requests.RequestException as exc:
            last_error = exc
    else:
        if last_error is not None:
            raise last_error
        raise RuntimeError("no Eastmoney quote endpoint configured")

    data = payload.get("data")

    if not data or str(data.get("f57")) != stock_code:
        return None

    _quote_cache[stock_code] = {"expires_at": now + CACHE_TTL_SECONDS, "data": data}
    return data


def format_quote(row: dict[str, Any]) -> dict[str, Any]:
    code = row.get("代码", row.get("f57"))
    name = row.get("名称", row.get("f58"))
    price = row.get("最新价", row.get("f43"))
    change_pct = row.get("涨跌幅", row.get("f170"))
    turnover = row.get("成交额", row.get("f48"))
    market_cap = row.get("总市值", row.get("f116"))
    float_market_cap = row.get("流通市值", row.get("f117"))
    pe_ttm = row.get("市盈率-动态", row.get("f162"))
    pb = row.get("市净率", row.get("f167"))

    return {
        "code": str(code),
        "name": str(name),
        "price": safe_float(price),
        "change_pct": safe_float(change_pct),
        "turnover": safe_float(turnover),
        "market_cap": safe_float(market_cap, 100000000),
        "float_market_cap": safe_float(float_market_cap, 100000000),
        "pe_ttm": safe_float(pe_ttm),
        "pb": safe_float(pb),
        "source": "东方财富",
    }


def get_stock_quote(code: str) -> dict[str, Any] | None:
    try:
        return fetch_stock_quote(code)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail="行情数据源暂时不可用") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="行情数据源暂时不可用") from exc


@app.get("/")
def home():
    return {"message": "Stock GPT API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/quote")
def get_quote(code: str = Query(..., description="A股代码，例如 688535、301150、000001.SZ")):
    stock_code = normalize_code(code)
    row = get_stock_quote(stock_code)

    if row is None:
        return {"error": f"未找到股票代码 {stock_code}"}

    return format_quote(row)


@app.get("/quotes")
def get_quotes(codes: str = Query(..., description="多个股票代码，用英文逗号分隔，例如 688535,301150,603186")):
    code_list = [normalize_code(code) for code in codes.split(",") if normalize_code(code)]

    result = []
    for code in code_list:
        row = get_stock_quote(code)
        if row is None:
            result.append({"code": code, "error": "未找到"})
            continue
        result.append(format_quote(row))

    return {"data": result}
