"""Streamable HTTP MCP, the slice the gateway and the seed use.

The server speaks protocol 2025-11-25. It lists two tools and does not hide either
of them: a denial is the gateway's decision on tools/call, not a missing tool.
"""

import json
import secrets

PROTOCOL = "2025-11-25"
SERVER_NAME = "Specialty Underwriting MCP"
SERVER_VERSION = "1.0.0"

TOOLS = (
    {
        "name": "get_submission_context",
        "description": "Read one synthetic specialty submission.",
        "inputSchema": {
            "type": "object",
            "properties": {"submission_id": {"type": "string"}},
            "required": ["submission_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mark_ready_for_quote",
        "description": "Mark one synthetic submission ready for quote. This does not bind coverage.",
        "inputSchema": {
            "type": "object",
            "properties": {"submission_id": {"type": "string"}},
            "required": ["submission_id"],
            "additionalProperties": False,
        },
    },
)


class ProtocolError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


def initialize(params):
    asked = (params or {}).get("protocolVersion")
    version = PROTOCOL if asked in (None, PROTOCOL) else PROTOCOL
    return {
        "protocolVersion": version,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": "Synthetic specialty review. The gateway decides each tool call.",
    }


def list_tools():
    return {"tools": [dict(tool) for tool in TOOLS]}


def tool_result(payload):
    text = json.dumps(payload, sort_keys=True)
    return {"content": [{"type": "text", "text": text}], "structuredContent": payload, "isError": False}


def success(message_id, result):
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def failure(message_id, code, message):
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def new_session():
    return secrets.token_urlsafe(18)
