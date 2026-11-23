# Shared Services API

## What it is

A small read-only HTTP API that exposes a deterministic catalog of shared platform services and their current status. It is the mock backend for the API self-service lifecycle playground. The service does not enforce authentication and does not call external systems. Because it serves public read-only data, it does not validate the HTTP Host header (including on the container health check at `GET /health`).

## Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Container health check (`{"status": "ok"}`) |
| GET | `/openapi.json` | OpenAPI 3.0.3 document |
| GET | `/v1/health` | API health (`{"status": "ok"}`) |
| GET | `/v1/services` | List all services with count |
| GET | `/v1/services/{id}` | One service or 404 |
| GET | `/v2/services` | Version 2.0 of the catalog. Each service includes `channel` |
| GET | `/v2/services/{id}` | One version 2.0 service, or 404 |
| GET | `/v1/notices` | Operational notices |
| GET | `/v1/notices/{id}` | One notice or 404 |

The same routes are available under a context prefix when a gateway forwards that prefix: `/shared-services`, `/shared-services-v2`, and `/platform-notices`.

## Environment

| Name | Meaning | Default |
| --- | --- | --- |
| `HTTP_PORT` | TCP port the server listens on | `8000` |

## Run

```sh
pip install -r requirements.txt
python server.py
```

Or build and run the Docker image from this directory.

## Tests

From this directory:

```sh
python3 -m unittest discover -s tests -t .
```

`httpx2` in `requirements.txt` is only required for `starlette.testclient.TestClient` in the tests.
