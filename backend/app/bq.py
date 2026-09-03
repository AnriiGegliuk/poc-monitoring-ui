"""Thin BigQuery query helper. Only used when USE_MOCK_DATA=false."""

from functools import lru_cache

from google.cloud import bigquery

from app.config import get_settings


@lru_cache
def _client() -> bigquery.Client:
    return bigquery.Client(project=get_settings().gcp_project_id)


def run_query(sql: str, params: dict | None = None) -> list[dict]:
    """Run a parameterized query, return rows as plain dicts (JSON-safe)."""
    job_config = None
    if params:
        query_params = [_scalar_param(name, value) for name, value in params.items()]
        job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    rows = _client().query(sql, job_config=job_config).result()
    return [_row_to_dict(row) for row in rows]


def _scalar_param(name: str, value) -> bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter:
    if isinstance(value, (list, tuple)):
        inner_type = "STRING" if not value or isinstance(value[0], str) else "INT64"
        return bigquery.ArrayQueryParameter(name, inner_type, list(value))
    if isinstance(value, bool):
        return bigquery.ScalarQueryParameter(name, "BOOL", value)
    if isinstance(value, int):
        return bigquery.ScalarQueryParameter(name, "INT64", value)
    if isinstance(value, float):
        return bigquery.ScalarQueryParameter(name, "FLOAT64", value)
    return bigquery.ScalarQueryParameter(name, "STRING", value)


def _row_to_dict(row: bigquery.table.Row) -> dict:
    out = dict(row.items())
    for key, value in out.items():
        # datetimes/dates aren't JSON-serializable as-is
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out
