# Review agent

## What it is

A deterministic runner for the hosted client `cyber-review-agent`. It obtains that client's credential, exchanges the underwriter token, checks the delegated token, and calls the gateway. It does not call a model. It does not send the underwriter token to the gateway.

## Endpoints

| Method | Path | Effect |
|---|---|---|
| GET | `/health` | Ready |
| POST | `/act` | `action` of `read` or `mark-ready`, plus `subject_token`, `expected_sub`, and `submission_id` |

A failed check returns `failed_closed` and does not call the gateway.

## Environment

| Variable | Meaning |
|---|---|
| `HTTP_PORT` | Listen port, default `8000` |
| `TOKEN_URL` | Access Management token endpoint |
| `CLIENT_ID` | `cyber-review-agent` |
| `CLIENT_SECRET` | That client's secret |
| `EXPECTED_ACTOR` | Required `act.sub` |
| `RESOURCE_URL` | Resource indicator on the exchange |
| `ALLOWED_AUDIENCES` | Comma-separated audiences the delegated token may carry |
| `GATEWAY_MCP_URL` | MCP proxy |

## Run

`python server.py` with the variables above set.

## Tests

`python -m unittest discover -s tests -t .`
