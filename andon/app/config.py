from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://andon:andon_dev@localhost:5432/andon"
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    openai_api_key: str | None = None
    designer_phone_number: str | None = None
    jim_phone_number: str | None = None
    clint_phone_number: str | None = None
    log_level: str = "INFO"
    quiet_hours_start: int = 7
    quiet_hours_end: int = 19
    base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env")

    def get_base_url(self) -> str:
        return self.base_url.rstrip("/")


settings = Settings()
