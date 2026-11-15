from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://naliwatch:naliwatch@localhost:5432/naliwatch"
    redis_url: str = "redis://localhost:6379/0"
    auto_create_tables: bool = True
    cors_origins: str = "http://localhost:3000"

    # auth
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 480
    otp_ttl_seconds: int = 300
    otp_dev_echo: bool = False

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"
    ai_daily_call_cap: int = 2000
    ai_confidence_threshold: float = 0.5

    # speech to text
    stt_provider: str = "none"  # whisper | bhashini | none
    openai_api_key: str = ""

    # channels
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    sms_webhook_url: str = ""

    # storage
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "ap-south-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    media_dir: str = "./media"
    max_upload_mb: int = 8

    # routing
    osrm_url: str = "https://router.project-osrm.org"

    # ---- decisions the plan leaves open (placeholders) ----
    volume_tolerance_pct: float = 10.0
    volume_tolerance_min_litres: int = 100
    fill_limit: float = 0.33
    sludge_litres_per_person_day: float = 0.15
    manual_cleaning_responder_phone: str = ""
    gps_ping_interval_seconds: int = 30
    gps_gap_minutes: int = 10
    retention_photo_days: int = 180
    retention_gps_days: int = 90
    trip_window_hours: int = 12
    default_job_litres: int = 1000

    # abuse limits
    report_rate_limit_per_hour: int = 10
    dedupe_radius_m: int = 50
    dedupe_hours: int = 6

    # clustering
    cluster_eps_m: int = 150
    cluster_min_samples: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
