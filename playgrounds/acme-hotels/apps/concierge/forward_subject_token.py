"""The concierge forwards the guest's token. The booking desk is the one that exchanges it.

The workshop agent exchanges a bearer before every MCP call. This process is that agent, and its
only call is the desk, so the exchange would happen one hop too soon. Replacing that step leaves
the guest's token as it arrived. This process has no Access Management client.
"""

def subject_token(authorization):
    """The bearer value, or none when the header is missing or is not a bearer token."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def install():
    """The workshop's token step returns the guest's token unchanged."""
    import agent.main as agent_main

    async def forward_subject_token(self, authorization):
        return subject_token(authorization)

    agent_main.MCPAgent.get_mcp_token = forward_subject_token


if __name__ == "__main__":
    import sys

    from agent.main import main

    install()
    sys.argv[0] = sys.argv[0].removesuffix(".exe")
    raise SystemExit(main())
