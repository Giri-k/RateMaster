from dataclasses import dataclass

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    default_rate_limit: int = 60
    default_window_seconds: int = 60

    model_config = {"env_prefix": "RATEMASTER_"}


settings = Settings()


@dataclass
class RuleConfig:
    algorithm: str
    limit: int
    window: int


RATE_LIMIT_RULES: dict[str, RuleConfig] = {
    "/api/login": RuleConfig(algorithm="sliding", limit=5, window=60),
    "/api/search": RuleConfig(algorithm="token", limit=20, window=60),
    "/api/status": RuleConfig(algorithm="fixed", limit=100, window=60),
    "default": RuleConfig(algorithm="fixed", limit=60, window=60),
}
