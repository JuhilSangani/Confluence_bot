# ------
# Config.py file is single source file for all the configuration.
# Every module reads settings from here.
# ------

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """
    Pydantic's BaseSettings automatically reads from your .env file.
    If a required key is missing, it raises a clear error at startup
    — not silently at runtime when it's too late.
    """

    APP_NAME: str = "ConfluenceBot"
    APP_VERSION: str = "0.1.0"

    class Config:
        env_file = ".env",  #Tells Pydantic where to find .env file
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """
    @lru_cache ensures this function runs only ONCE — on the first call.
    After that, Python returns the cached Settings object directly.
    """
    return Settings()
