import uuid

import boto3
from botocore.config import Config

from app.core.config import settings

_s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)


def upload_file(data: bytes, content_type: str, folder: str = "photos") -> str:
    ext = _ext_from_mime(content_type)
    key = f"{folder}/{uuid.uuid4().hex}{ext}"
    _s3.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def delete_file(key: str) -> None:
    _s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)


def get_public_url(key: str) -> str:
    if settings.R2_PUBLIC_URL:
        return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"
    return f"https://{settings.R2_BUCKET_NAME}.r2.dev/{key}"


def _ext_from_mime(mime: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(mime, "")
