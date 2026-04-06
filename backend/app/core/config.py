import os
from pydantic_settings import BaseSettings
from pydantic import model_validator
from typing import Literal


class Settings(BaseSettings):
    RAIN_ENV: Literal["development", "staging", "production", "test"] = "development"
    RAIN_VERSION: str = "6.0.0"
    RAIN_LOG_LEVEL: str = "debug"

    DATABASE_URL: str = "postgresql+asyncpg://rain_app:rain@localhost:5432/rain"
    # Canonical name is VALKEY_URL. REDIS_URL accepted for backward compat.
    VALKEY_URL: str = "redis://valkey:6379/0"
    # Backward compatibility: accept REDIS_URL env var
    REDIS_URL: str | None = None

    S3_BUCKET: str = "rain-audio"
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"

    JWT_SECRET_KEY: str = "dev-secret-key-do-not-use-in-production"
    JWT_ALGORITHM: str = "RS256"
    JWT_PUBLIC_KEY_PATH: str = "/etc/rain/jwt.pub"
    JWT_PRIVATE_KEY_PATH: str = "/etc/rain/jwt.key"

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_SPARK_MONTHLY: str = ""
    STRIPE_PRICE_CREATOR_MONTHLY: str = ""
    STRIPE_PRICE_ARTIST_MONTHLY: str = ""
    STRIPE_PRICE_STUDIO_PRO_MONTHLY: str = ""

    RAIN_NORMALIZATION_VALIDATED: bool = False
    ANTHROPIC_API_KEY: str = ""
    ONNX_MODEL_PATH: str = "/models/rain_base.onnx"
    GENRE_CLASSIFIER_ENABLED: bool = False
    CODEC_NET_ENABLED: bool = False
    ATMOS_HRTF_PATH: str = ""

    FRONTEND_URL: str = "http://localhost:5173"

    # Distribution
    LABELGRID_API_KEY: str = ""
    LABELGRID_API_BASE: str = "https://api.labelgrid.com/v1"
    LABELGRID_SANDBOX: bool = True
    ISRC_REGISTRANT_CODE: str = "ARC"
    UPC_GS1_PREFIX: str = "000000"

    # Content scan
    AUDD_API_TOKEN: str = ""
    ACRCLOUD_HOST: str = ""
    ACRCLOUD_ACCESS_KEY: str = ""
    ACRCLOUD_ACCESS_SECRET: str = ""

    # Provenance (C2PA + AudioSeal) — EU AI Act Art. 50 compliance (2026-08-02)
    C2PA_SIGNING_CERT_PATH: str = "/etc/rain/c2pa-cert.pem"
    C2PA_SIGNING_KEY_PATH: str = "/etc/rain/c2pa-key.pem"
    AUDIOSEAL_MODEL_PATH: str = "/models/audioseal_generator.pth"
    AUDIOSEAL_KEY_SEED: int = 42  # per-deployment 16-bit message base
    RAIN_CERT_SIGNING_KEY_PATH: str = "/etc/rain/cert.key"
    RAIN_WATERMARK_KEY_PATH: str = "/etc/rain/wm.key"

    # Separation (BS-RoFormer 4-pass cascade) — GPU worker paths
    BSROFORMER_MODEL_PATH: str = "ml/checkpoints/bs_roformer_sw.ckpt"
    BSROFORMER_CONFIG_PATH: str = "ml/checkpoints/bs_roformer_sw.yaml"
    KARAOKE_MODEL_PATH: str = "ml/checkpoints/karaoke_bs_roformer.ckpt"
    KARAOKE_CONFIG_PATH: str = "ml/checkpoints/karaoke_bs_roformer.yaml"
    DRUMSEP_MODEL_PATH: str = "ml/checkpoints/drumsep.ckpt"
    DRUMSEP_CONFIG_PATH: str = "ml/checkpoints/drumsep.yaml"
    DEREVERB_MODEL_PATH: str = "ml/checkpoints/dereverb_melband_roformer.ckpt"
    DEREVERB_CONFIG_PATH: str = "ml/checkpoints/dereverb_melband_roformer.yaml"
    BSROFORMER_DEVICE: str = "cuda:0"
    SEPARATION_ENABLED: bool = False  # flip on once ALL 4 checkpoints are provisioned

    # R6 WASM binary integrity — SHA-256 of deployed rain_dsp.wasm.
    # When set, every session's wasm_binary_hash must match or RAIN-E304 fires.
    RAIN_EXPECTED_WASM_HASH: str = os.getenv("RAIN_EXPECTED_WASM_HASH", "")

    @model_validator(mode="after")
    def _compat_redis_url(self) -> "Settings":
        """If REDIS_URL is set but VALKEY_URL is at default, use REDIS_URL."""
        if self.REDIS_URL and self.VALKEY_URL == "redis://valkey:6379/0":
            self.VALKEY_URL = self.REDIS_URL
        return self

    @model_validator(mode="after")
    def check_production_secrets(self) -> "Settings":
        if self.RAIN_ENV == "production":
            if self.JWT_SECRET_KEY == "dev-secret-key-do-not-use-in-production":
                raise ValueError("JWT_SECRET_KEY must be set to a real secret in production")
            if self.S3_ACCESS_KEY == "minioadmin":
                raise ValueError("S3_ACCESS_KEY must not use dev defaults in production")
        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
