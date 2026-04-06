"""
Async S3 storage service for RAIN.

Uses aioboto3 for non-blocking S3 operations. Audio never leaves the device
during processing unless the user explicitly initiates upload for distribution
or collaboration.

S3 key format: users/{user_id}/{session_id}/{file_hash}.{ext} — IMMUTABLE.
"""

import hashlib
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aioboto3
import structlog
from botocore.exceptions import ClientError

from app.core.config import settings

logger = structlog.get_logger(__name__)

_session: aioboto3.Session | None = None


def _get_session() -> aioboto3.Session:
    """Return a module-level aioboto3 session (lazy-initialized, reusable)."""
    global _session
    if _session is None:
        _session = aioboto3.Session(
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )
    return _session


@asynccontextmanager
async def _s3_client() -> AsyncIterator:
    """Yield an async S3 client from the session."""
    session = _get_session()
    async with session.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
    ) as client:
        yield client


def s3_key(user_id: str, session_id: str, file_hash: str, ext: str) -> str:
    """Canonical S3 key format. IMMUTABLE: users/{user_id}/{session_id}/{file_hash}.{ext}"""
    return f"users/{user_id}/{session_id}/{file_hash}.{ext}"


async def upload_to_s3(
    data: bytes,
    user_id: str,
    session_id: str,
    filename: str,
    content_type: str = "audio/wav",
) -> tuple[str, str]:
    """Upload file to S3. Returns (s3_key, sha256_hash).

    Raises:
        ClientError: On S3 operation failure.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
    file_hash = hashlib.sha256(data).hexdigest()
    key = s3_key(user_id, session_id, file_hash, ext)

    log = logger.bind(
        user_id=user_id,
        session_id=session_id,
        stage="upload",
        s3_key=key,
        size_bytes=len(data),
    )

    start_ms = time.monotonic()
    try:
        async with _s3_client() as client:
            await client.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata={"sha256": file_hash, "user_id": user_id},
            )
        duration_ms = round((time.monotonic() - start_ms) * 1000)
        log.info("s3_upload_success", duration_ms=duration_ms)
        return key, file_hash
    except ClientError as exc:
        duration_ms = round((time.monotonic() - start_ms) * 1000)
        log.error(
            "s3_upload_failed",
            error=str(exc),
            error_code="RAIN-E501",
            duration_ms=duration_ms,
        )
        raise


async def download_from_s3(key: str) -> bytes:
    """Download an object from S3 by key.

    Raises:
        ClientError: On S3 operation failure (including NoSuchKey).
    """
    log = logger.bind(stage="download", s3_key=key)
    start_ms = time.monotonic()
    try:
        async with _s3_client() as client:
            response = await client.get_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
            )
            data: bytes = await response["Body"].read()
        duration_ms = round((time.monotonic() - start_ms) * 1000)
        log.info("s3_download_success", size_bytes=len(data), duration_ms=duration_ms)
        return data
    except ClientError as exc:
        duration_ms = round((time.monotonic() - start_ms) * 1000)
        log.error(
            "s3_download_failed",
            error=str(exc),
            error_code="RAIN-E502",
            duration_ms=duration_ms,
        )
        raise


async def delete_from_s3(key: str) -> None:
    """Delete an object from S3 by key.

    Raises:
        ClientError: On S3 operation failure.
    """
    log = logger.bind(stage="delete", s3_key=key)
    start_ms = time.monotonic()
    try:
        async with _s3_client() as client:
            await client.delete_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
            )
        duration_ms = round((time.monotonic() - start_ms) * 1000)
        log.info("s3_delete_success", duration_ms=duration_ms)
    except ClientError as exc:
        duration_ms = round((time.monotonic() - start_ms) * 1000)
        log.error(
            "s3_delete_failed",
            error=str(exc),
            error_code="RAIN-E503",
            duration_ms=duration_ms,
        )
        raise


async def generate_presigned_url(key: str, expires_seconds: int = 3600) -> str:
    """Generate a presigned GET URL for the given S3 key.

    Raises:
        ClientError: On S3 operation failure.
    """
    log = logger.bind(stage="presign", s3_key=key)
    try:
        async with _s3_client() as client:
            url: str = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET, "Key": key},
                ExpiresIn=expires_seconds,
            )
        log.info("s3_presign_success", expires_seconds=expires_seconds)
        return url
    except ClientError as exc:
        log.error(
            "s3_presign_failed",
            error=str(exc),
            error_code="RAIN-E504",
        )
        raise


async def head_object(key: str) -> dict:
    """Retrieve metadata for an S3 object without downloading it.

    Raises:
        ClientError: On S3 operation failure (including 404 if key does not exist).
    """
    log = logger.bind(stage="head", s3_key=key)
    try:
        async with _s3_client() as client:
            response = await client.head_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
            )
        log.info("s3_head_success")
        return {
            "content_length": response.get("ContentLength"),
            "content_type": response.get("ContentType"),
            "last_modified": response.get("LastModified"),
            "metadata": response.get("Metadata", {}),
        }
    except ClientError as exc:
        log.error(
            "s3_head_failed",
            error=str(exc),
            error_code="RAIN-E505",
        )
        raise
