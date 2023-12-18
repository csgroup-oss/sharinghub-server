# Copyright 2023-2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of SharingHUB project
#     https://gitlab.si.c-s.fr/space_applications/mlops-services/sharinghub-server
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

from io import BytesIO
import logging
from typing import Annotated

import boto3
from botocore.exceptions import ClientError
from fastapi import (
    APIRouter,
    HTTPException,
    Path,
    Request,
    Response,
)
from fastapi.responses import JSONResponse, RedirectResponse
from botocore.exceptions import BotoCoreError, ClientError
from app.dependencies import GitlabTokenDep

from app.api.gitlab import GitlabClient
from app.config import GITLAB_URL

router = APIRouter()


LOGGER = logging.getLogger(__name__)

router = APIRouter()

S3_BUCKET = "gitlab"
S3_ACCESS_KEY = "minioadmin"
S3_SECRET_KEY = "minioadmin"
S3_REGION_NAME = "test"
S3_ENDPOINT_URL = "http://127.0.0.1:9000"
S3_PRESIGNED_EXPIRATION = 3600

# TODO : store configuration
s3_client = boto3.client(
    "s3",
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION_NAME,
    endpoint_url=S3_ENDPOINT_URL,
)

# Chunck size for upload to S3
S3_UPLOAD_LEN = 6000000


async def check_access(token, project_id):
    """
    Checks the access permissions for a given Gitlab user token and project ID.

    Parameters:
    - token (str): Gitlab authentication token.
    - project_id (int): Identifier for the project to be checked.

    Returns:
    - bool: True if the user has access to the specified project, False otherwise.

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


# OK
# PUT : curl -L  -d @README.md -X PUT  -H 'Content-Type:application/octet-stream' -H 'X-Gitlab-Token:toto'  http://localhost:19422/store/1243/README.md
# GET : curl -L -H 'X-Gitlab-Token:toto'  http://localhost:19422/store/1243/README.md
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
    check_access(token, project_id)

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
        # TODO 
        logging.error(e)
        return e

    return RedirectResponse(response)


# OK
# curl -d @README.md -H 'X-Gitlab-Token:toto'  http://localhost:19422/store/1244/README.md
@router.post(
    "/{project_id:str}/{path:path}",
    description="Create S3 redirect URL for given S3 Service",
)
async def s3_post_proxy(
    project_id: Annotated[str, Path(title="The ID of the item to get")],
    path: Annotated[str, Path(title="The ID of the item to get")],
    request: Request,
    token: GitlabTokenDep,
):
    check_access(token, project_id)

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
            if byte_buffer_size > S3_UPLOAD_LEN:
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
        LOGGER.error(e)
        raise HTTPException(status_code=500, detail=f"Error connecting to AWS S3: {e}")
    except ClientError as e:
        LOGGER.error(e)
        raise HTTPException(status_code=500, detail=f"AWS S3 Client Error: {e}")
