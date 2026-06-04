"""analytics.crm — SQLite-backed Application CRM.

All functions accept a ``db_path`` parameter so tests can use tmp_path.
List/dict columns are JSON-encoded in the DB and decoded on read.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from decroche.models import Application

_CREATE = """
CREATE TABLE IF NOT EXISTS applications (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
)
"""


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(_CREATE)
    conn.commit()
    return conn


def _serialize(app: Application) -> str:
    return app.model_dump_json()


def _deserialize(raw: str) -> Application:
    return Application.model_validate_json(raw)


# ── public API ─────────────────────────────────────────────────────────────────


def track(app: Application, db_path: str) -> Application:
    """Insert or replace an Application in the CRM.

    Args:
        app:     The Application to persist.
        db_path: Absolute path to the SQLite database file.

    Returns:
        The persisted Application (same object).
    """
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO applications (id, data) VALUES (?, ?)",
            (app.id, _serialize(app)),
        )
        conn.commit()
    return app


def get(app_id: str, db_path: str) -> Application | None:
    """Retrieve an Application by id.

    Args:
        app_id:  The application id.
        db_path: Path to the SQLite database file.

    Returns:
        Application if found, None otherwise.
    """
    with _connect(db_path) as conn:
        row = conn.execute("SELECT data FROM applications WHERE id = ?", (app_id,)).fetchone()
    if row is None:
        return None
    return _deserialize(row[0])


def update_stage(
    app_id: str,
    new_stage: str,
    db_path: str,
    note: str | None = None,
) -> Application:
    """Transition an Application to a new stage, appending history.

    Args:
        app_id:    The application id.
        new_stage: The target stage string.
        db_path:   Path to the SQLite database file.
        note:      Optional note to attach to the history entry.

    Returns:
        The updated Application.

    Raises:
        KeyError: if the application does not exist.
    """
    existing = get(app_id, db_path)
    if existing is None:
        raise KeyError(f"Application not found: {app_id!r}")

    history_entry: dict = {
        "stage": new_stage,
        "at": datetime.now(tz=timezone.utc).isoformat(),
    }
    if note is not None:
        history_entry["note"] = note

    updated = existing.model_copy(
        update={
            "stage": new_stage,
            "stage_history": existing.stage_history + [history_entry],
        }
    )
    track(updated, db_path)
    return updated


def list_apps(db_path: str, stage: str | None = None) -> list[Application]:
    """Return all Applications, optionally filtered by stage.

    Args:
        db_path: Path to the SQLite database file.
        stage:   If given, only return applications with this stage.

    Returns:
        List of Application objects.
    """
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT data FROM applications").fetchall()
    apps = [_deserialize(row[0]) for row in rows]
    if stage is not None:
        apps = [a for a in apps if a.stage == stage]
    return apps
