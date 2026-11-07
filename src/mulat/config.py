"""Application settings from environment / ConfigMap."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # Ollama / OpenAI-compatible proxy (e.g. http://localhost:11434/v1)
    openai_api_base: str = ""

    prometheus_url: str = "http://localhost:9090"
    prometheus_verify_ssl: bool = True
    database_url: str = ""
    slack_webhook_url: str = ""

    mulat_host: str = "0.0.0.0"
    mulat_port: int = 8000
    log_level: str = "INFO"

    # Optional: remote API (overrides kubeconfig). Example: https://192.168.1.10:6443
    k8s_api_server: str = ""
    k8s_token: str = ""
    k8s_verify_ssl: bool = True

    k8s_api_timeout_seconds: int = 15
    prometheus_query_timeout_seconds: int = 30


settings = Settings()
