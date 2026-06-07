"""analytics.crm — SQLite-backed CRM for tracking job applications.

Schema
------
applications
    id          TEXT PRIMARY KEY
    data        TEXT  (JSON blob — full Application serialised with model_dump_json)
    stage       TEXT
    updated_at  TEXT  (ISO-8601)

Design decisions
----------------
- Single JSON column avoids schema migrations when Application evolves.
- All callers pass an absolute db_path (resolved by resolve_data_path before
  reaching this layer in the MCP tool wrappers).
- SQLite WAL mode for concurrent read safety.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from decroche.models import Application
from decroche.storage import resolve_data_path


def _connect(db_path: str) -> sqlite3.Connection:
    """Open (and initialise if new) the SQLite CRM database."""
    p = resolve_data_path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id         TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            stage      TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def track(app: Application, db_path: str) -> Application:
    """Insert or replace an Application record.

    Args:
        app:     Application to persist.
        db_path: Absolute or relative path to the SQLite file.

    Returns:
        The persisted Application (identity — same object).
    """
    now = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO applications (id, data, stage, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (app.id, app.model_dump_json(), app.stage, now),
        )
    return app


def get(app_id: str, db_path: str) -> Optional[Application]:
    """Fetch a single Application by id, or None if not found.

    Args:
        app_id:  The application id to look up.
        db_path: Path to the SQLite file.

    Returns:
        Application if found, else None.
    """
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT data FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
    if row is None:
        return None
    return Application.model_validate_json(row[0])


def update_stage(
    app_id: str,
    new_stage: str,
    db_path: str,
    note: str | None = None,
) -> Application:
    """Transition an Application to a new stage and append a history entry.

    Args:
        app_id:    Id of the application to update.
        new_stage: Target pipeline stage.
        db_path:   Path to the SQLite file.
        note:      Optional text note to attach to the history entry.

    Returns:
        Updated Application.

    Raises:
        KeyError: if app_id is not found in the database.
    """
    app = get(app_id, db_path)
    if app is None:
        raise KeyError(f"Application {app_id!r} not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    entry: dict = {"stage": new_stage, "at": now_iso}
    if note:
        entry["note"] = note

    updated = app.model_copy(
        update={
            "stage": new_stage,
            "history": (app.history or []) + [entry],
        }
    )
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE applications SET data = ?, stage = ?, updated_at = ? WHERE id = ?",
            (updated.model_dump_json(), new_stage, now_iso, app_id),
        )
    return updated


def list_apps(db_path: str, stage: str | None = None) -> list[Application]:
    """Return all tracked Applications, optionally filtered by stage.

    Args:
        db_path: Path to the SQLite file.
        stage:   If given, only return applications in this stage.

    Returns:
        List of Application objects ordered by updated_at DESC.
    """
    with _connect(db_path) as conn:
        if stage is None:
            rows = conn.execute(
                "SELECT data FROM applications ORDER BY updated_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT data FROM applications WHERE stage = ? ORDER BY updated_at DESC",
                (stage,),
            ).fetchall()
    return [Application.model_validate_json(r[0]) for r in rows]
