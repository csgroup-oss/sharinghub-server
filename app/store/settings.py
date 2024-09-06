# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of SharingHub project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
S3_CHECK_ACCESS_CACHE_TIMEOUT: float = conf(
    "s3.check-access.cache-timeout",
    "S3_CHECK_ACCESS_CACHE_TIMEOUT",
    default=60.0 * 5,
    cast=float,
)
