"""Atlas Session Lifecycle — FastMCP server entry point.

Modular monolith: two domains (session + contract) registered on
a single FastMCP server. Stateless tools, file-based state.

Run:
    python -m atlas_session.server              # stdio (Claude Code)
    python -m atlas_session.server --transport http  # HTTP (remote)
"""

import sys

from fastmcp import FastMCP

from .session import tools as session_tools
from .contract import tools as contract_tools

mcp = FastMCP(
    "Atlas Session Lifecycle",
    version="4.0.0",
    instructions=(
        "MCP server for AI session lifecycle management. "
        "Manages session context, soul purpose tracking, governance, "
        "and deterministic contract-based bounty verification."
    ),
)

# Register both domains
session_tools.register(mcp)
contract_tools.register(mcp)


def main():
    """Entry point for both `python -m atlas_session.server` and pip script."""
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
