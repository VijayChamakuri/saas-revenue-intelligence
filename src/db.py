"""Small DuckDB helpers shared by the analytics and validation entry points."""

from __future__ import annotations

from typing import Any

import duckdb


def fetch_row(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[Any, ...]:
    """Return the first row of a query, failing loudly if the query returns nothing."""
    row = con.execute(sql).fetchone()
    if row is None:
        raise LookupError(f"Query returned no rows: {' '.join(sql.split())[:120]}")
    return row
