import io
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name="us-east-1",
        )
        self.bucket = settings.S3_BUCKET_NAME

    def ensure_bucket_exists(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            logger.info("s3_bucket_exists", bucket=self.bucket)
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            if error_code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self.bucket)
                logger.info("s3_bucket_created", bucket=self.bucket)
            else:
                raise

    def upload_bundle(self, file_bytes: bytes, filename: str, tenant_id: str) -> str:
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"{tenant_id}/{timestamp}-{unique_id}-{filename}"
        self._client.upload_fileobj(
            io.BytesIO(file_bytes),
            self.bucket,
            s3_key,
            ExtraArgs={"ContentType": "application/octet-stream"},
        )
        logger.info("bundle_uploaded", s3_key=s3_key, size=len(file_bytes))
        return s3_key

    def download_bundle(self, s3_key: str) -> bytes:
        buf = io.BytesIO()
        self._client.download_fileobj(self.bucket, s3_key, buf)
        buf.seek(0)
        logger.info("bundle_downloaded", s3_key=s3_key)
        return buf.read()

    def delete_bundle(self, s3_key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=s3_key)
        logger.info("bundle_deleted", s3_key=s3_key)


storage_service = StorageService()
