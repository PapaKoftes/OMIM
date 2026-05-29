"""OMIM configuration."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global OMIM settings, loaded from environment / .env file."""

    # Paths
    data_dir: Path = Field(default=Path("data"), alias="OMIM_DATA_DIR")
    log_level: str = Field(default="INFO", alias="OMIM_LOG_LEVEL")

    # Featherless AI (LLM semantic annotation)
    featherless_api_key: str = Field(default="", alias="FEATHERLESS_API_KEY")
    featherless_base_url: str = Field(
        default="https://api.featherless.ai/v1", alias="FEATHERLESS_BASE_URL"
    )
    featherless_model: str = Field(default="deepseek-chat", alias="FEATHERLESS_MODEL")

    # Versions (frozen for hackathon)
    ontology_version: str = "v0.1.0"
    ruleset_version: str = "v0.1.0"
    schema_version: str = "v0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def ontology_dir(self) -> Path:
        return self.data_dir / "ontology"

    @property
    def rules_dir(self) -> Path:
        return self.data_dir / "rules"

    @property
    def fixtures_dir(self) -> Path:
        return self.data_dir / "fixtures"


_settings: Settings | None = None


def get_settings() -> Settings:
    """Lazy singleton for settings."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
