from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Nexa Store"
    database_url: str = "sqlite:///./data/nexa_store.db"
    admin_api_key: str = "nexa-dev-admin"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    telegram_bot_token: str = ""
    telegram_admin_id: str = ""
    telegram_timeout_seconds: float = 5.0
    execution_max_workers: int = 4
    browser_headless: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
