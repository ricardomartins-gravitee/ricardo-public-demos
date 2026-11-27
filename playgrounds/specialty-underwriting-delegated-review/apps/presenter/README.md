# Underwriting desk

## What it is

The desk an underwriter uses. The cyber review agent sits on the same file. The browser talks only to this process. Delegated actions go to the agent. **Mark ready myself** calls the same gateway tool with the underwriter token.

## Endpoints

| Method | Path | Effect |
|---|---|---|
| GET | `/` | The page |
| GET | `/health` | Ready |
| GET | `/api/ready` | Agent and submission service health |
| GET | `/api/desk` | Session and file status. Risk facts are not included |
| POST | `/api/sign-in/start` | Authorization URL for the popup |
| GET | `/callback` | Completes the code exchange |
| POST | `/api/read-through-agent` | Delegated read |
| POST | `/api/mark-through-agent` | Delegated write, expected to be denied |
| POST | `/api/mark-myself` | Direct human write |
| POST | `/api/reset` | Restores `CYB-001` and drops the session |

A POST that is not JSON is refused. A POST from another site is refused. `/health` answers any host.

## Environment

| Variable | Meaning |
|---|---|
| `HTTP_PORT` | Listen port, default `8000` |
| `ALLOWED_HOSTS` | Comma-separated host names |
| `AM_PUBLIC_ISSUER` | Issuer the browser uses |
| `TOKEN_URL` | Token endpoint this process uses |
| `WEB_CLIENT_ID` | `specialty-underwriting-web` |
| `WEB_CLIENT_SECRET` | That client's secret |
| `REDIRECT_URL` | Registered callback |
| `AGENT_URL` | Agent runner |
| `GATEWAY_MCP_URL` | MCP proxy |
| `SUBMISSIONS_URL` | Private observation and reset |
| `CONTROL_TOKEN` | Header for those calls |
| `DECISIONS_URL` | Gamma decisions address |

## Run

`python server.py` with those variables set. Open `/`.

## Tests

`python -m unittest discover -s tests -t .`
