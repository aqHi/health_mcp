from functools import lru_cache
from pydantic import BaseSettings, AnyUrl
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Health MCP Server"
    app_env: str = "dev"
    app_port: int = 8000

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "password"
    mysql_db: str = "health_mcp"
    mysql_driver: str = "mysql+pymysql"
    database_url: Optional[str] = None

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url: Optional[AnyUrl] = None

    api_key: Optional[str] = None
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"{self.mysql_driver}://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
