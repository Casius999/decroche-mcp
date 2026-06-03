from fastmcp import FastMCP

mcp = FastMCP("decroche-mcp")


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
