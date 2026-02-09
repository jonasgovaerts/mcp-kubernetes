from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    KUBECONFIG: str | None = None

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
