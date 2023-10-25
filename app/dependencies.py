from collections import namedtuple
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN

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


GitlabTokenDep = Annotated[GitlabToken, Depends(get_gitlab_token)]
