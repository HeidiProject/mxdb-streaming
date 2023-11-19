import uuid
from pydantic_settings import BaseSettings, SettingsConfigDict

# Implemented Pydantic Settings for the ENV variables
# https://docs.pydantic.dev/latest/concepts/pydantic_settings/
class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "your_database_name"
    user_collection_name: str = "Users"
    stream_collection_name: str = "Stream"
    api_key: uuid.uuid4 

    origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:5173",
    "https://mx-webapps.psi.ch",
    "https://heidi-test.psi.ch",
    "https://heidi.psi.ch"
    # Add more allowed origins as needed
    ]

    # https://docs.pydantic.dev/latest/concepts/pydantic_settings/#dotenv-env-support
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
