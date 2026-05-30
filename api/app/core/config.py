import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AlphaAgents"
    api_v1_prefix: str = "/api/v1"
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    data_db: str = "data/alphaagents.db"
    workflow_db: str = "data/alphaagents-workflows.db"
    tdx_root: str = ""
    external_data_live_enabled: bool = False
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-reasoner"
    llm_timeout_seconds: float = 60.0
    selection_data_source: str = "local"
    selection_stock_pool: str = ""
    cors_origins: str = (
        "http://127.0.0.1:5173,"
        "http://localhost:5173,"
        "http://127.0.0.1:3000,"
        "http://localhost:3000,"
        "http://127.0.0.1:5500,"
        "http://localhost:5500,"
        "null"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ALPHAAGENTS_",
        extra="ignore",
    )

    @property
    def resolved_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_selection_stock_pool(self) -> list[str]:
        return [
            symbol.strip().upper()
            for symbol in self.selection_stock_pool.split(",")
            if symbol.strip()
        ]

    @property
    def resolved_llm_api_key(self) -> str:
        return self.llm_api_key or os.getenv("DEEPSEEK_API_KEY", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
