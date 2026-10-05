from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class RiakSettings(BaseModel):
    base_url: str
    timeout: float


class AuthSettings(BaseModel):
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    cookie_secure: bool
    cookie_httponly: bool
    cookie_samesite: Literal["lax", "strict", "none"]


class PostgresSettings(BaseModel):
    host: str
    port: int
    user: str
    password: str
    db: str
    min_connections: int
    max_connections: int

    @property
    def conninfo(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class CouchDbSettings(BaseModel):
    node0_url: str
    node1_url: str
    user: str
    password: str
    products_db: str
    categories_db: str
    timeout: float

    @property
    def nodes(self) -> list[str]:
        return [self.node0_url, self.node1_url]


class Settings(BaseSettings):
    riak: RiakSettings
    postgres: PostgresSettings
    auth: AuthSettings
    couchdb: CouchDbSettings

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_nested_delimiter="__",
        extra="ignore",
    )


# noinspection PyArgumentList
settings = Settings()
