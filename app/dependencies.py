from collections import namedtuple
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN

from app.config import REMOTES
from app.utils.http import slugify, url_domain

gitlab_token_query = APIKeyQuery(
    name="gitlab_token", scheme_name="GitLab Private Token query", auto_error=False
)
gitlab_token_header = APIKeyHeader(
    name="X-Gitlab-Token", scheme_name="GitLab Private Token header", auto_error=False
)
GitlabToken = namedtuple("GitlabToken", ["value", "query"])


async def get_gitlab_token(
    query_param: Annotated[str, Security(gitlab_token_query)],
    header_param: Annotated[str, Security(gitlab_token_header)],
) -> GitlabToken:
    if query_param:
        return GitlabToken(value=query_param, query=dict(gitlab_token=query_param))
    elif header_param:
        return GitlabToken(value=header_param, query=dict())
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="An API key must be passed as query or header",
        )


async def get_gitlab_config(gitlab: str) -> dict:
    for remote_name, remote_config in REMOTES.items():
        url: str = remote_config.get("url", "")
        if url_domain(url) == gitlab:
            return {
                **remote_config,
                "name": remote_name,
                "url": url.removesuffix("/"),
                "path": gitlab,
            }
    return {
        "name": slugify(gitlab).replace("-", ""),
        "url": f"https://{gitlab}",
        "path": gitlab,
    }


GitlabTokenDep = Annotated[GitlabToken, Depends(get_gitlab_token)]
GitlabConfigDep = Annotated[dict, Depends(get_gitlab_config)]
