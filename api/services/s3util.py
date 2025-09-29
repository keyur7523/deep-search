import os, boto3
_s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)
_BUCKET = os.getenv("S3_BUCKET","")

def presign_put_url(key: str, content_type: str) -> str:
    return _s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": _BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=900,
    )
