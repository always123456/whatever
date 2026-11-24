from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JM_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    debug: bool = False
    database_url: str = "sqlite:///./job_match.db"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24
    top_n: int = 10
    embedding_backend: str = "keyword"  # keyword | semantic
    semantic_model: str = "BAAI/bge-small-zh-v1.5"


settings = Settings()
