from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, FilePath


class PipelineConfig(BaseSettings):
    taxi_zones_file: FilePath


class PostgresConfig(BaseSettings):
    host: str
    port: int
    db: str
    user: str
    password: str

    def uri(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="app_", env_nested_delimiter="__")

    host: str = "127.0.0.1"
    port: int = 80
    raw_db: PostgresConfig = Field(default_factory=PostgresConfig)  # type: ignore
    analytics_db: PostgresConfig = Field(default_factory=PostgresConfig)  # type: ignore
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)  # type: ignore
