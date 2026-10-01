from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADRIVA_", env_file=".env", extra="ignore")
    database_url: SecretStr = SecretStr("postgresql://adriva@127.0.0.1:55432/adriva")
    migration_database_url: SecretStr | None = None
    environment: Literal["development", "test", "production"] = "development"
    artifact_root: Path = Path(".local/artifacts")
    max_import_cases: int = 1000

    @model_validator(mode="after")
    def validate_environment(self) -> "Settings":
        if not self.database_url.get_secret_value().startswith("postgresql://"):
            raise ValueError("PostgreSQL connection URL required")
        if self.environment == "production":
            raise ValueError("Production startup is disabled until authentication is implemented")
        if not 1 <= self.max_import_cases <= 10000:
            raise ValueError("max_import_cases must be in 1..10000")
        return self
