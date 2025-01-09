# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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

import logging
from io import BytesIO
from typing import Annotated

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.status import HTTP_403_FORBIDDEN

from app.auth import GitlabTokenDep
from app.auth.api import GitlabToken
from app.providers.client.gitlab import GitlabClient
from app.providers.schemas import AccessLevel
from app.settings import CHECKER_CACHE_TIMEOUT, GITLAB_URL
from app.stac.api.category import FeatureVal
from app.utils.cache import cache

from .settings import (
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_CHECK_ACCESS_CACHE_TIMEOUT,
    S3_ENDPOINT_URL,
    S3_FEATURE_NAME,
    S3_PRESIGNED_EXPIRATION,
    S3_REGION_NAME,
    S3_SECRET_KEY,
    S3_UPLOAD_CHUNK_SIZE,
)

logger = logging.getLogger("app")

router = APIRouter()


s3_client = boto3.client(
    "s3",
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION_NAME,
    endpoint_url=S3_ENDPOINT_URL,
)


async def check_access(token: GitlabToken, project_id: int) -> None:
    """Checks the access permissions for a given Gitlab user token and project ID."""
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    user: str | None = await cache.get(token.value, namespace="user")
    if not user:
        user = await gitlab_client.get_user()
        await cache.set(token.value, user, namespace="user")

    project_path: str | None = await cache.get(project_id, namespace="project-path")
    if not project_path:
        project_path = await gitlab_client.get_project_path(id=project_id)
        await cache.set(
            project_id,
            project_path,
            ttl=int(CHECKER_CACHE_TIMEOUT),
            namespace="project-path",
        )

    has_access: bool | None = await cache.get(
        (user, project_path), namespace="project-access"
    )
    if has_access is None:
        project = await gitlab_client.get_project(project_path)
        if any(
            c.features.get(S3_FEATURE_NAME, FeatureVal.DISABLE) != FeatureVal.ENABLE
            for c in project.categories
        ):
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="S3 store is not enabled for this project's category",
            )
        has_access = project.access_level >= AccessLevel.CONTRIBUTOR
        await cache.set(
            (user, project_path),
            has_access,
            ttl=int(S3_CHECK_ACCESS_CACHE_TIMEOUT),
            namespace="project-access",
        )

    if not has_access:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Insufficient access level, must be at least developer.",
        )


@router.api_route(
    "/{project_id}/{path:path}",
    methods=["PUT", "GET", "HEAD"],
    description="Create S3 redirect URL for given S3 Service",
)
async def s3_get_proxy(
    project_id: int,
    path: str,
    request: Request,
    token: GitlabTokenDep,
) -> RedirectResponse:
    await check_access(token, project_id)

    try:
        s3_path = f"{project_id}/{path}"
        if request.method in ["PUT"]:
            response = s3_client.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": S3_BUCKET,
                    "Key": s3_path,
                    "ContentType": "application/octet-stream",
                },
                ExpiresIn=S3_PRESIGNED_EXPIRATION,
            )
        else:
            response = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": s3_path},
                ExpiresIn=S3_PRESIGNED_EXPIRATION,
            )
    except ClientError as e:
        detail = f"AWS S3 Client Error: {e}"
        raise HTTPException(status_code=500, detail=detail) from e

    return RedirectResponse(response)


@router.post(
    "/{project_id}/{path:path}",
    description="Create S3 redirect URL for given S3 Service",
)
async def s3_post_proxy(
    project_id: Annotated[int, Path(title="The ID of the item to get")],
    path: Annotated[str, Path(title="The path of the item to get")],
    request: Request,
    token: GitlabTokenDep,
) -> JSONResponse:
    await check_access(token, project_id)

    try:
        s3_path = f"{project_id}/{path}"
        byte_buffer = BytesIO()

        # Stream the file directly to S3 without loading it entirely into memory
        mpu = s3_client.create_multipart_upload(Bucket=S3_BUCKET, Key=s3_path)
        upload_id = mpu["UploadId"]
        part_number = 1
        parts = []
        byte_buffer_size = 0
        async for chunk in request.stream():
            byte_buffer.write(chunk)
            byte_buffer_size += len(chunk)
            if byte_buffer_size > S3_UPLOAD_CHUNK_SIZE:
                byte_buffer.seek(0)
                part = s3_client.upload_part(
                    Bucket=S3_BUCKET,
                    Key=s3_path,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=byte_buffer.read(byte_buffer_size),
                )
                parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
                part_number += 1
                byte_buffer.seek(0)
                byte_buffer_size = 0

        if byte_buffer_size > 0:
            byte_buffer.seek(0)
            part = s3_client.upload_part(
                Bucket=S3_BUCKET,
                Key=s3_path,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=byte_buffer.read(byte_buffer_size),
            )
            parts.append({"PartNumber": part_number, "ETag": part["ETag"]})

        part_info = {"Parts": parts}

        s3_client.complete_multipart_upload(
            Bucket=S3_BUCKET,
            Key=s3_path,
            UploadId=mpu["UploadId"],
            MultipartUpload=part_info,
        )

        return JSONResponse(
            content={"message": "File uploaded successfully"},
            status_code=200,
        )

    except BotoCoreError as e:
        detail = f"Error connecting to AWS S3: {e}"
        raise HTTPException(status_code=500, detail=detail) from e
    except ClientError as e:
        detail = f"AWS S3 Client Error: {e}"
        raise HTTPException(status_code=500, detail=detail) from e
