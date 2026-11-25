# Submission service

## What it is

The private record for one synthetic cyber submission, and the MCP endpoint the gateway proxies. It does not decide who may call a tool.

## Tools

| Tool | Effect |
|---|---|
| `get_submission_context` | Returns `CYB-001`. Does not change status. |
| `mark_ready_for_quote` | Moves `IN_REVIEW` to `READY_FOR_QUOTE` and counts the call. Does not bind coverage. |

`GET /health` is open. `GET /demo/observation` and `POST /demo/reset` require `X-Demo-Control`.

## Environment

| Variable | Meaning | Default |
|---|---|---|
| `HTTP_PORT` | Listen port | `8000` |
| `CONTROL_TOKEN` | Reset and observation header | required |

## Run

`python server.py` from this directory, with `CONTROL_TOKEN` set.

## Tests

`python -m unittest discover -s tests -t .`
