import boto3
from botocore.config import Config
from core.config import settings


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key,
        aws_secret_access_key=settings.r2_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


async def upload_to_r2(content: bytes, key: str, content_type: str = "image/jpeg") -> str:
    """Upload bytes to R2 and return the public URL."""
    client = _get_client()
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=content,
        ContentType=content_type,
    )
    return f"{settings.r2_public_url}/{key}"


async def upload_capture(frame_bytes: bytes, log_id: str) -> str:
    key = f"captures/{log_id}.jpg"
    return await upload_to_r2(frame_bytes, key, "image/jpeg")


def get_signed_url(key: str, expires: int = 3600) -> str:
    """Generate a temporary signed URL for private media."""
    client = _get_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=expires,
    )
