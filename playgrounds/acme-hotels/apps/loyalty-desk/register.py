"""Serves the loyalty desk and registers it in the local AWS account.

The gateway calls this process. A background registration creates the Bedrock AgentCore runtime
``acme_hotels_loyalty`` in MiniStack, so the account lists the same agent Gravitee calls. MiniStack is
not asked to start a container: the catalog does not allow it to mount the Docker socket, and without
that socket an invocation only echoes.
"""

import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import loyalty

NAME = "acme_hotels_loyalty"
PORT = int(os.environ.get("REGISTER_PORT", "8090"))
IMAGE = os.environ.get(
    "LOYALTY_IMAGE",
    "ghcr.io/ricardomartins-gravitee/ricardo-public-demos/acme-hotels-plus-loyalty:latest",
)
ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://acme-hotels-plus-ministack:4566")
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
ROLE = "arn:aws:iam::000000000000:role/acme-hotels-loyalty"


def runtime_spec():
    """The AgentCore runtime this process registers. The name is the one the account shows."""
    return {
        "agentRuntimeName": NAME,
        "description": "ACME Hotels loyalty desk",
        "agentRuntimeArtifact": {"containerConfiguration": {"containerUri": IMAGE}},
        "roleArn": ROLE,
        "networkConfiguration": {"networkMode": "PUBLIC"},
        "environmentVariables": {
            "LLM_BASE_URL": os.environ.get("LLM_BASE_URL", "http://apim-gateway:8082/llm-proxy"),
            "LLM_MODEL": os.environ.get("LLM_MODEL", "ollama:gemma4:12b"),
            "MCP_URL": os.environ.get("MCP_URL", "http://apim-gateway:8082/hotels-mcp/mcp"),
        },
    }


def control_client():
    """The AgentCore control client, pointed at the local AWS account."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "bedrock-agentcore-control",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 2}),
    )


def ensure_runtime(control):
    """The runtime's ARN, creating it when the account does not have it yet."""
    from botocore.exceptions import ClientError

    try:
        created = control.create_agent_runtime(**runtime_spec())
        return created["agentRuntimeArn"]
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code != "ConflictException":
            raise
    listed = control.list_agent_runtimes().get("agentRuntimes") or []
    for item in listed:
        if item.get("agentRuntimeName") == NAME:
            return item["agentRuntimeArn"]
    raise RuntimeError("The loyalty runtime already exists and it was not listed")


def wait_runtime(control):
    """The runtime ARN, once the local AWS account answers."""
    deadline = time.monotonic() + 60
    while True:
        try:
            return ensure_runtime(control)
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def serve():
    """The address the gateway calls. Registration does not delay it."""

    class Desk(BaseHTTPRequestHandler):
        server_version = "acme-hotels-loyalty"

        def do_GET(self):
            status, payload, content_type = loyalty.respond("GET", self.path, b"")
            self._send(status, payload, content_type)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            status, payload, content_type = loyalty.respond("POST", self.path, self.rfile.read(length))
            self._send(status, payload, content_type)

        def log_message(self, fmt, *args):
            return

        def _send(self, status, payload, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    ThreadingHTTPServer(("0.0.0.0", PORT), Desk).serve_forever()


def main():
    def register():
        try:
            wait_runtime(control_client())
        except Exception as error:
            print(f"The loyalty runtime was not registered: {error}", flush=True)

    threading.Thread(target=register, daemon=True).start()
    serve()


if __name__ == "__main__":
    main()
