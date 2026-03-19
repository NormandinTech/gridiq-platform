"""
GridIQ — Application configuration
Loads from environment variables / .env file using Pydantic Settings.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "GridIQ Platform"
    app_version: str = "1.0.0"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # ── API ──────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://gridiq:password@localhost:5432/gridiq_db"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_telemetry_channel: str = "gridiq:telemetry"
    redis_alert_channel: str = "gridiq:alerts"
    redis_threat_channel: str = "gridiq:threats"

    # ── Kafka ────────────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_telemetry: str = "gridiq.telemetry"
    kafka_topic_alerts: str = "gridiq.alerts"
    kafka_topic_commands: str = "gridiq.commands"
    kafka_consumer_group: str = "gridiq-backend"

    # ── MQTT ─────────────────────────────────────────────────────────────────
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str = "gridiq"
    mqtt_password: str = ""
    mqtt_topic_prefix: str = "gridiq/"

    # ── Auth ─────────────────────────────────────────────────────────────────
    jwt_secret_key: str = "CHANGE_THIS_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # ── Weather API ──────────────────────────────────────────────────────────
    openweather_api_key: str = ""
    weather_lat: float = 37.7749
    weather_lon: float = -122.4194
    weather_forecast_hours: int = 48

    # ── ML ───────────────────────────────────────────────────────────────────
    ml_models_dir: str = "./ml_models"
    demand_forecast_model: str = "demand_tft_v1.pt"
    anomaly_model: str = "anomaly_isolation_forest_v1.pkl"
    asset_health_model: str = "asset_health_xgb_v1.pkl"

    # ── Simulation (dev) ─────────────────────────────────────────────────────
    simulate_telemetry: bool = True
    simulation_interval_seconds: int = 5
    simulation_num_assets: int = 50

    # ── Notifications ────────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    alert_email_recipients: str = ""
    slack_webhook_url: str = ""

    # ── Compliance ───────────────────────────────────────────────────────────
    compliance_report_dir: str = "./reports/compliance"
    audit_log_retention_days: int = 365
    nerc_region: str = "WECC"

    # ── Feature flags ────────────────────────────────────────────────────────
    feature_digital_twin: bool = True
    feature_cybersecurity: bool = True
    feature_advanced_ml: bool = True
    feature_grid_simulation: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance. Use as FastAPI dependency."""
    return Settings()


settings = get_settings()
