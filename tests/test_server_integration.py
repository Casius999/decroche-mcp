import pytest
from fastmcp import Client

from decroche.server import mcp


@pytest.mark.asyncio
async def test_tools_registered():
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        assert any(n.endswith("parse") for n in names)        # cv_parse
        assert any("market" in n for n in names)               # market.*


@pytest.mark.asyncio
async def test_call_cv_parse(fixtures_dir):
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        parse_name = next(n for n in names if n.endswith("parse"))
        res = await client.call_tool(parse_name, {"path": str(fixtures_dir / "sample_en.txt")})
        # res.structured_content is a dict; res.data is a Root Pydantic object
        data = res.structured_content
        assert data["json_resume"]["basics"]["email"] == "jane.doe@example.com"


@pytest.mark.asyncio
async def test_call_market_get_default_fr():
    async with Client(mcp) as client:
        names = [t.name for t in await client.list_tools()]
        get_name = next(n for n in names if n.endswith("market_get"))
        res = await client.call_tool(get_name, {})
        # res.structured_content is a dict
        data = res.structured_content
        assert data["id"] == "fr"
