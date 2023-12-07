from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

# Implemented Pydantic Settings for the ENV variables
# https://docs.pydantic.dev/latest/concepts/pydantic_settings/
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    mongodb_url: str 
    database_name: str 
    user_collection_name: str 
    stream_collection_name: str 
    vespa_collection_name: str

    # https://docs.pydantic.dev/latest/concepts/pydantic_settings/#dotenv-env-support
