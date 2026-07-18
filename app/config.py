from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    app_env: str = "development"
    app_port: int = 8000
    vault_path: str = ""
    db_path: str = "govi.db"
    fernet_key: str = ""
    jwt_secret: str = ""
    super_admin_email: str = ""
    super_admin_password: str = ""
    fb_app_id: str = ""
    fb_app_secret: str = ""
    fb_redirect_uri: str = ""
    internal_secret: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
