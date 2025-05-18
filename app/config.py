from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    tripo_api_key: str
    openai_api_key: str
    redis_url: str = "redis://localhost:6379/0" # Default Redis URL
    # Add other settings here as needed

    model_config = SettingsConfigDict(env_file='.env')

settings = Settings() 