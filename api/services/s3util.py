import os
import logging

logger = logging.getLogger(__name__)

_s3 = None
_BUCKET = None

def _get_s3_client():
    """Lazy initialization of S3 client with validation"""
    global _s3, _BUCKET
    
    if _s3 is not None:
        return _s3
    
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION")
    _BUCKET = os.getenv("S3_BUCKET", "")
    
    if not all([access_key, secret_key, region, _BUCKET]):
        logger.warning("⚠️ S3 not configured - missing AWS credentials or bucket name")
        return None
    
    import boto3
    _s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    logger.info("✅ S3 client initialized")
    return _s3

def presign_put_url(key: str, content_type: str) -> str:
    """Generate presigned URL for S3 upload"""
    client = _get_s3_client()
    if client is None:
        raise RuntimeError("S3 not configured - missing AWS credentials or bucket name")
    
    return client.generate_presigned_url(
        "put_object",
        Params={"Bucket": _BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=900,
    )
