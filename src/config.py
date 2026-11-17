"""Settings come from environment variables, never from hardcoded values."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    s3_bucket: str
    s3_prefix: str
    aws_profile: str | None
    aws_region: str
    database_url: str


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing environment variable {name}. Copy .env.example to .env and fill it in."
        )
    return value


def load_config() -> Config:
    load_dotenv()
    return Config(
        s3_bucket=_required("S3_BUCKET"),
        s3_prefix=os.getenv("S3_PREFIX", "incoming/"),
        aws_profile=os.getenv("AWS_PROFILE") or None,
        aws_region=os.getenv("AWS_REGION", "ap-northeast-1"),
        database_url=_required("DATABASE_URL"),
    )
