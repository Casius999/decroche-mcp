from fastmcp import FastMCP

from decroche.cv import cv_server
from decroche.market import market_server

mcp = FastMCP("decroche-mcp")
mcp.mount(cv_server, namespace="cv")
mcp.mount(market_server, namespace="market")


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
