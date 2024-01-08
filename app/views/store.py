import logging
from io import BytesIO
from typing import Annotated

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.gitlab import GitlabClient
from app.config import GITLAB_URL
from app.dependencies import GitlabTokenDep

logger = logging.getLogger("app")

router = APIRouter()

S3_BUCKET = "gitlab"
S3_ACCESS_KEY = "minioadmin"
S3_SECRET_KEY = "minioadmin"
S3_REGION_NAME = "test"
S3_ENDPOINT_URL = "http://127.0.0.1:9000"
S3_PRESIGNED_EXPIRATION = 3600
S3_UPLOAD_CHUNK_SIZE = 6000000

s3_client = boto3.client(
    "s3",
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION_NAME,
    endpoint_url=S3_ENDPOINT_URL,
)


async def check_access(token, project_id):
    """
    Checks the access permissions for a given Gitlab user token and project ID.

    Raises:
    - AuthenticationError: If the provided token is invalid or expired.
    - ProjectNotFoundError: If the specified project ID does not exist.
    - AccessDeniedError: If the user does not have the necessary permissions for the project.
    - Other custom exceptions may be raised based on specific implementation details.
    """

    # TODO : Implement
    gitlab_client = GitlabClient(url=GITLAB_URL, token=token.value)
    # ...
    # raise HTTPException(status_code=403, detail="Access denied")

    return True


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
) -> Response:
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
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"AWS S3 Client Error: {e}")

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
):
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
            content={"message": "File uploaded successfully"}, status_code=200
        )

    except BotoCoreError as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"Error connecting to AWS S3: {e}")
    except ClientError as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"AWS S3 Client Error: {e}")
