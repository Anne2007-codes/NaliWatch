import os
from pathlib import Path

from ..config import settings

_s3 = None


def _client():
    global _s3
    if _s3 is None:
        import boto3

        _s3 = boto3.client(
            "s3", region_name=settings.s3_region, endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key or None, aws_secret_access_key=settings.s3_secret_key or None,
        )
    return _s3


def put(key: str, data: bytes, content_type: str = "image/jpeg") -> str:
    if settings.s3_bucket:
        _client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
    else:
        p = Path(settings.media_dir) / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return key


def signed_url(key: str, expires: int = 900) -> str:
    if settings.s3_bucket:
        return _client().generate_presigned_url("get_object", Params={"Bucket": settings.s3_bucket, "Key": key}, ExpiresIn=expires)
    return f"local://{key}"  # dev only; files live under MEDIA_DIR


def delete(key: str) -> None:
    if settings.s3_bucket:
        _client().delete_object(Bucket=settings.s3_bucket, Key=key)
    else:
        try:
            os.remove(Path(settings.media_dir) / key)
        except FileNotFoundError:
            pass
