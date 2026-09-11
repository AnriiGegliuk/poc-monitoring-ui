from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime config, all overridable via env vars / .env. See .env.example."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default is real BigQuery via Application Default Credentials. Set to
    # true only for offline dev/demo without touching production data.
    use_mock_data: bool = False

    gcp_project_id: str = "langx-production"
    bq_reports_dataset: str = "dbt_reports"
    bq_raw_dataset: str = "dqa_pipeline"

    cache_ttl_seconds: int = 300
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def reports_ref(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_reports_dataset}"

    @property
    def raw_ref(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_raw_dataset}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
