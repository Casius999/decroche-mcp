"""analytics sub-package — FastMCP sub-server for CRM + funnel analytics."""

from __future__ import annotations

from fastmcp import FastMCP

from decroche.analytics.crm import list_apps as _list_apps
from decroche.analytics.crm import track as _track
from decroche.analytics.crm import update_stage as _update_stage
from decroche.analytics.extras import channel_roi
from decroche.analytics.extras import salary_delta
from decroche.analytics.extras import story_coverage
from decroche.analytics.funnel import funnel as _funnel
from decroche.models import Application, FunnelStats, SalaryRange, Story

__all__ = [
    "analytics_server",
    "channel_roi",
    "story_coverage",
    "salary_delta",
]

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


@analytics_server.tool
def channel_roi_tool(apps: list[Application]) -> dict:
    """Compute interview and offer rates by source_channel.

    Args:
        apps: List of Application objects.

    Returns:
        Dict keyed by source_channel with ``{count, interview_rate, offer_rate}``.
    """
    return channel_roi(apps)


@analytics_server.tool
def story_coverage_tool(stories: list[Story], target_competencies: list[str]) -> dict:
    """Report which competencies have at least one story and which are gaps.

    Args:
        stories:              List of Story objects.
        target_competencies:  Competencies to check coverage for.

    Returns:
        Dict with ``covered`` (list), ``gaps`` (list), ``coverage_pct`` (float).
    """
    return story_coverage(stories, target_competencies)


@analytics_server.tool
def salary_delta_tool(offer: dict, benchmark: SalaryRange) -> dict:
    """Compare an offer amount to benchmark P50 and P75.

    Args:
        offer:     Dict with ``base`` (numeric) and optionally ``currency``.
        benchmark: SalaryRange from ``negotiate.benchmark_range``.

    Returns:
        Dict with ``offer_base``, ``p50``, ``p75``, ``delta_p50``,
        ``delta_p75``, ``delta_p50_pct``, ``delta_p75_pct``,
        ``vs_p50`` (``"above"`` / ``"at"`` / ``"below"``), ``currency``.
    """
    return salary_delta(offer, benchmark)
