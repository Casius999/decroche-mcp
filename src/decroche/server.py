from fastmcp import FastMCP

from decroche.ats import ats_server
from decroche.cv import cv_server
from decroche.market import market_server
from decroche.match import match_server

mcp = FastMCP("decroche-mcp")
mcp.mount(cv_server, namespace="cv")
mcp.mount(market_server, namespace="market")
mcp.mount(ats_server, namespace="ats")
mcp.mount(match_server, namespace="match")


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
