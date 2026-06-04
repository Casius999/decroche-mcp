from fastmcp import FastMCP

from decroche.analytics import analytics_server
from decroche.apply import apply_server
from decroche.ats import ats_server
from decroche.cv import cv_server
from decroche.market import market_server
from decroche.match import match_server
from decroche.network import network_server
from decroche.recruiter import recruiter_server
from decroche.source import source_server

mcp = FastMCP("decroche-mcp")
mcp.mount(cv_server, namespace="cv")
mcp.mount(market_server, namespace="market")
mcp.mount(ats_server, namespace="ats")
mcp.mount(match_server, namespace="match")
mcp.mount(source_server, namespace="source")
mcp.mount(recruiter_server, namespace="recruiter")
mcp.mount(network_server, namespace="network")
mcp.mount(apply_server, namespace="apply")
mcp.mount(analytics_server, namespace="analytics")


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
