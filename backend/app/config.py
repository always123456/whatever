from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JM_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    debug: bool = False
    database_url: str = "postgresql+psycopg://job_match@127.0.0.1:5432/job_match"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 60 * 24
    top_n: int = 10
    embedding_backend: str = "keyword"  # keyword | semantic
    semantic_model: str = "BAAI/bge-small-zh-v1.5"
    # —— LLM（DeepSeek，OpenAI 兼容协议），用于公司特质语义打分 ——
    llm_api_key: str = ""                      # 留空则回退环境变量 DEEPSEEK_API_KEY / 注册表
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_timeout: float = 30.0


settings = Settings()
