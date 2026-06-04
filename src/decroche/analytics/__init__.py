"""analytics sub-package — FastMCP sub-server for CRM + funnel analytics."""

from __future__ import annotations

from fastmcp import FastMCP

from decroche.analytics.crm import list_apps as _list_apps
from decroche.analytics.crm import track as _track
from decroche.analytics.crm import update_stage as _update_stage
from decroche.analytics.funnel import funnel as _funnel
from decroche.models import Application, FunnelStats

analytics_server = FastMCP("analytics")


@analytics_server.tool
def track(app: Application, db_path: str) -> Application:
    """Track (insert or update) an Application in the CRM.

    Args:
        app:     The Application to persist.
        db_path: Absolute path to the SQLite database file.

    Returns:
        The persisted Application.
    """
    return _track(app, db_path)


@analytics_server.tool
def update_stage(
    app_id: str,
    new_stage: str,
    db_path: str,
    note: str | None = None,
) -> Application:
    """Transition an Application to a new stage.

    Appends a history entry with timestamp (and optional note).

    Args:
        app_id:    The application id.
        new_stage: Target stage.
        db_path:   Path to the SQLite database file.
        note:      Optional human note to attach.

    Returns:
        Updated Application.
    """
    return _update_stage(app_id, new_stage, db_path, note=note)


@analytics_server.tool
def list_apps(db_path: str, stage: str | None = None) -> list[Application]:
    """Return all tracked Applications, optionally filtered by stage.

    Args:
        db_path: Path to the SQLite database file.
        stage:   Optional stage filter.

    Returns:
        List of Application objects.
    """
    return _list_apps(db_path, stage=stage)


@analytics_server.tool
def funnel(apps: list[Application]) -> FunnelStats:
    """Compute conversion funnel statistics over a list of Applications.

    Args:
        apps: List of Application objects.

    Returns:
        FunnelStats with counts, rates, bottleneck, vs_benchmark, notes.
    """
    return _funnel(apps)
