# uses pydantic_settings to get keys stored in the .env file in which we are going to use in the app
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    DATABASE_URL : str


    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

