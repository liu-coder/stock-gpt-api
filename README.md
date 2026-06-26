# Stock GPT API

FastAPI service for querying China A-share quote snapshots from Eastmoney.

## Endpoints

- `GET /health` - health check for deployment platforms.
- `GET /quote?code=000001` - query one A-share stock.
- `GET /quotes?codes=000001,600000` - query multiple A-share stocks.

Common code formats are accepted, including `000001`, `000001.SZ`, `sz000001`,
`600000.SH`, and `sh600000`.

## Local Run

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the interactive API docs.

## Render

This repository includes `render.yaml`. Render will install dependencies from
`requirements.txt` and run:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```
