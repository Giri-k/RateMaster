from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    default_rate_limit: int = 60
    default_window_seconds: int = 60

    model_config = {"env_prefix": "RATEMASTER_"}


settings = Settings()
