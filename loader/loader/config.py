from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, FilePath


class LoaderConfig(BaseSettings):
    csv_path: FilePath


class PostgresConfig(BaseSettings):
    host: str
    port: int
    db: str
    user: str
    password: str

    def uri(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="app_", env_nested_delimiter="__")

    host: str = "127.0.0.1"
    port: int = 80
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)  # type: ignore
    loader: LoaderConfig = Field(default_factory=LoaderConfig)  # type: ignore
