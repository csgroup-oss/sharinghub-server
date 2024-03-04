import logging
from io import BytesIO
from typing import Annotated

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.auth import GitlabTokenDep
from app.auth.api import GitlabToken
from app.providers.client import GitlabClient
from app.settings import GITLAB_URL
from app.stac.api.category import FeatureVal

from .settings import (
    S3_ACCESS_KEY,
    S3_BUCKET,
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


async def check_access(token: GitlabToken, project_id: str) -> None:
    """Checks the access permissions for a given Gitlab user token and project ID."""
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    project = await gitlab_client.get_project_from_id(id=int(project_id))
    if (
        project.category.features.get(S3_FEATURE_NAME, FeatureVal.DISABLE)
        != FeatureVal.ENABLE
    ):
        raise HTTPException(
            status_code=403,
            detail="S3 store is not enabled for this project's category",
        )


@router.api_route(
    "/{project_id:str}/{path:path}",
    methods=["PUT", "GET", "HEAD"],
    description="Create S3 redirect URL for given S3 Service",
)
async def s3_get_proxy(
    project_id: str,
    path: str,
    request: Request,
    token: GitlabTokenDep,
) -> RedirectResponse:
    await check_access(token, project_id)

    try:
        s3_path = project_id + "/" + path
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
    "/{project_id:str}/{path:path}",
    description="Create S3 redirect URL for given S3 Service",
)
async def s3_post_proxy(
    project_id: Annotated[str, Path(title="The ID of the item to get")],
    path: Annotated[str, Path(title="The path of the item to get")],
    request: Request,
    token: GitlabTokenDep,
) -> JSONResponse:
    await check_access(token, project_id)

    try:
        s3_path = project_id + "/" + path

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
