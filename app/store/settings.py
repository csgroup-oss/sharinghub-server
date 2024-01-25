from app.settings import conf
from app.utils.config import cbool

S3_ENABLE: bool = conf("s3.enable", "S3_ENABLE", default=False, cast=cbool())
S3_BUCKET: str | None = conf("s3.bucket", "S3_BUCKET", cast=str)
S3_ACCESS_KEY: str | None = conf("s3.access-key", "S3_ACCESS_KEY", cast=str)
S3_SECRET_KEY: str | None = conf("s3.secret-key", "S3_SECRET_KEY", cast=str)
S3_REGION_NAME: str | None = conf("s3.region", "S3_REGION_NAME", cast=str)
S3_ENDPOINT_URL: str | None = conf("s3.endpoint", "S3_ENDPOINT_URL", cast=str)
S3_PRESIGNED_EXPIRATION: int = conf(
    "s3.presigned-expiration",
    "S3_PRESIGNED_EXPIRATION",
    default=3600,
    cast=int,
)
S3_UPLOAD_CHUNK_SIZE: int = conf(
    "s3.upload-chunk-size",
    "S3_UPLOAD_CHUNK_SIZE",
    default=6000000,
    cast=int,
)
S3_FEATURE_NAME = "store-s3"
