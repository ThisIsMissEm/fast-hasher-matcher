from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
  database_url: PostgresDsn

  role_matcher: bool = True
  role_hasher: bool = True
  role_curator: bool = True
  ui_enabled: bool = True

  allowed_hostnames: set[str] = set()
  max_content_length: int = 1 * 1024 * 1024  # 100MB max file size

  model_config = SettingsConfigDict(env_file=".env", env_prefix="OMM_")

settings = Settings()

settings.allowed_hostnames.add("github.com")
settings.allowed_hostnames.add("raw.githubusercontent.com")

def get_settings() -> Settings:
    return settings