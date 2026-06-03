from unittest.mock import patch


def test_server_module_exposes_mcp_and_main():
    from decroche import server

    assert hasattr(server, "mcp")
    assert callable(server.main)
    assert server.mcp.name == "decroche-mcp"


def test_main_calls_mcp_run():
    """Ensure main() delegates to mcp.run() without actually blocking."""
    from decroche import server

    with patch.object(server.mcp, "run") as mock_run:
        server.main()
        mock_run.assert_called_once()
