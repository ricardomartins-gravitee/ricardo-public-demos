"""The concierge forwards the guest's token. The booking desk is the one that exchanges it.

The workshop agent exchanges a bearer before every MCP call. This process is that agent, and its
only call is the desk, so the exchange would happen one hop too soon. Replacing that step leaves
the guest's token as it arrived. This process has no Access Management client.
"""

SPEAKERS = {
    "ask_booking_desk": "booking",
    "ask_loyalty_desk": "loyalty",
}


def speaker_of(tool_name):
    """The desk a tool asks, or the concierge when the turn called no desk."""
    return SPEAKERS.get(tool_name, "concierge")


def mark(speaker, text):
    """A prefix the website reads, then removes, to choose the agent's icon."""
    return f"[[acme-agent:{speaker}]]\n{text}"


def subject_token(authorization):
    """The bearer value, or none when the header is missing or is not a bearer token."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def install():
    """The workshop's token step returns the guest's token unchanged, and a reply names who answered."""
    import agent.main as agent_main
    import agent.mcp_client as mcp_client

    async def forward_subject_token(self, authorization):
        return subject_token(authorization)

    agent_main.MCPAgent.get_mcp_token = forward_subject_token

    original_call = mcp_client.MCPMultiClient.call_tool

    async def remember_tool(self, tool_name, arguments, extra_headers=None):
        self.last_tool_name = tool_name
        return await original_call(self, tool_name, arguments, extra_headers)

    mcp_client.MCPMultiClient.call_tool = remember_tool

    original_process = agent_main.MCPAgent.process

    async def marked_process(self, *args, **kwargs):
        mcp = getattr(self, "mcp", None)
        if mcp is not None:
            mcp.last_tool_name = None
        text, tool_messages = await original_process(self, *args, **kwargs)
        tool = getattr(mcp, "last_tool_name", None)
        return mark(speaker_of(tool), text), tool_messages

    agent_main.MCPAgent.process = marked_process


if __name__ == "__main__":
    import sys

    from agent.main import main

    install()
    sys.argv[0] = sys.argv[0].removesuffix(".exe")
    raise SystemExit(main())
